#!/usr/bin/env python3
"""Contract integration flow over RabbitMQ.

Simulates dealer tools (garages) and subsidiaries sending car-finance contracts
to a central system, the way an ESB / message bus decouples applications:

    producteur  --entrant.<pays>-->  [contrats]  -->  contrats.entrants
    controleur  applies the business control rules on every contract:
                  valid    --valide.<pays>-->  [contrats]  -->  contrats.valides
                  rejected --rejet.<regle>-->  [contrats.dlx] -->  contrats.rejets
                  unreadable  nack -> native dead-lettering  -->  contrats.rejets
    si-central  integrates the valid contracts

Every role exposes Prometheus metrics on METRICS_PORT so the rejection rate can
be followed per rule, per country and per source system in Grafana.
"""

import json
import logging
import os
import random
import signal
import sys
import time
import uuid
from datetime import date, timedelta

import pika
from prometheus_client import Counter, Histogram, start_http_server

ROLE = os.environ["ROLE"]  # producteur | controleur | si-central
AMQP_HOST = os.getenv("AMQP_HOST", "rabbitmq.integration.svc.cluster.local")
AMQP_USER = os.environ["RABBITMQ_USER"]
AMQP_PASSWORD = os.environ["RABBITMQ_PASSWORD"]
METRICS_PORT = int(os.getenv("METRICS_PORT", "8000"))
RATE = float(os.getenv("PRODUCER_RATE_PER_SECOND", "2"))
ERROR_RATIO = float(os.getenv("PRODUCER_ERROR_RATIO", "0.08"))
POISON_RATIO = float(os.getenv("PRODUCER_POISON_RATIO", "0.005"))

EXCHANGE = "contrats"
DLX = "contrats.dlx"
Q_IN = "contrats.entrants"
Q_OK = "contrats.valides"
Q_KO = "contrats.rejets"

COUNTRIES = ["FR", "ES", "IT", "DE", "PT", "BE"]
DURATIONS = [12, 24, 36, 48, 60, 72]
# Each source system has its own data quality, like real dealer tools.
SOURCES = {"dms-garage": 1.0, "portail-filiale": 0.4, "batch-legacy": 2.5}

log = logging.getLogger(ROLE)

EMITTED = Counter("contrats_emis_total", "Contracts sent by source systems", ["pays", "source"])
VALID = Counter("contrats_valides_total", "Contracts accepted by the control rules", ["pays", "source"])
REJECTED = Counter(
    "contrats_rejetes_total", "Contracts rejected by a control rule", ["pays", "source", "regle"]
)
UNREADABLE = Counter("contrats_illisibles_total", "Unparseable messages dead-lettered by the broker")
INTEGRATED = Counter("contrats_integres_total", "Contracts integrated by the central system", ["pays"])
CHECK_SECONDS = Histogram("contrats_controle_secondes", "Time spent applying the control rules")


# --------------------------------------------------------------------------- broker
def declare_topology(ch):
    """Idempotent: every role declares the topology it relies on."""
    ch.exchange_declare(EXCHANGE, exchange_type="topic", durable=True)
    ch.exchange_declare(DLX, exchange_type="topic", durable=True)
    ch.queue_declare(
        Q_IN,
        durable=True,
        arguments={
            "x-queue-type": "quorum",
            "x-dead-letter-exchange": DLX,
            "x-dead-letter-routing-key": "rejet.illisible",
            "x-delivery-limit": 3,  # poison messages cannot loop forever
        },
    )
    ch.queue_bind(Q_IN, EXCHANGE, routing_key="entrant.#")
    ch.queue_declare(Q_OK, durable=True, arguments={"x-queue-type": "quorum"})
    ch.queue_bind(Q_OK, EXCHANGE, routing_key="valide.#")
    ch.queue_declare(
        Q_KO,
        durable=True,
        arguments={"x-queue-type": "quorum", "x-max-length": 5000, "x-overflow": "drop-head"},
    )
    ch.queue_bind(Q_KO, DLX, routing_key="rejet.#")


def connect():
    params = pika.ConnectionParameters(
        host=AMQP_HOST,
        credentials=pika.PlainCredentials(AMQP_USER, AMQP_PASSWORD),
        heartbeat=30,
        blocked_connection_timeout=60,
        client_properties={"connection_name": f"contrats-flow-{ROLE}"},
    )
    while True:
        try:
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            ch.confirm_delivery()  # publisher confirms: no silent message loss
            declare_topology(ch)
            log.info("connected to %s", AMQP_HOST)
            return conn, ch
        except pika.exceptions.AMQPError as exc:
            log.warning("broker unavailable (%r), retrying in 5s", exc)
            time.sleep(5)


def publish(ch, exchange, routing_key, body, headers=None):
    ch.basic_publish(
        exchange=exchange,
        routing_key=routing_key,
        body=body,
        properties=pika.BasicProperties(
            content_type="application/json",
            delivery_mode=pika.DeliveryMode.Persistent,
            headers=headers or {},
        ),
        mandatory=True,  # raises UnroutableError if no queue is bound
    )


# --------------------------------------------------------------------------- producteur
DEFECTS = [
    lambda c: c.pop("client"),
    lambda c: c.update(montant=-c["montant"]),
    lambda c: c.update(duree_mois=99),
    lambda c: c.update(date_signature=(date.today() + timedelta(days=30)).isoformat()),
    lambda c: c.update(devise="USD"),
    lambda c: c.update(pays="XX"),
]


def make_contract():
    source = random.choice(list(SOURCES))
    contract = {
        "id": str(uuid.uuid4()),
        "pays": random.choice(COUNTRIES),
        "source": source,
        "client": f"C{random.randint(10000, 99999)}",
        "montant": round(random.uniform(3000, 60000), 2),
        "duree_mois": random.choice(DURATIONS),
        "devise": "EUR",
        "date_signature": (date.today() - timedelta(days=random.randint(0, 20))).isoformat(),
    }
    if random.random() < ERROR_RATIO * SOURCES[source]:
        random.choice(DEFECTS)(contract)
    return contract


def run_producteur(ch):
    while True:
        if random.random() < POISON_RATIO:
            publish(ch, EXCHANGE, "entrant.inconnu", b"<contrat>format inattendu</contrat>")
        else:
            contract = make_contract()
            publish(ch, EXCHANGE, f"entrant.{contract['pays']}", json.dumps(contract).encode())
            EMITTED.labels(contract["pays"], contract["source"]).inc()
        ch.connection.sleep(1 / RATE)  # keeps heartbeats flowing


# --------------------------------------------------------------------------- controleur
def _date_ok(c):
    return date.fromisoformat(c["date_signature"]) <= date.today()


RULES = [
    ("champ_obligatoire", lambda c: all(c.get(k) not in (None, "") for k in
                                        ("id", "pays", "client", "montant", "duree_mois", "date_signature"))),
    ("pays_inconnu", lambda c: c["pays"] in COUNTRIES),
    ("montant_invalide", lambda c: isinstance(c["montant"], (int, float)) and 0 < c["montant"] <= 150_000),
    ("duree_hors_bareme", lambda c: c["duree_mois"] in DURATIONS),
    ("date_future", _date_ok),
    ("devise_non_supportee", lambda c: c.get("devise") == "EUR"),
]


def first_failed_rule(contract):
    for name, check in RULES:
        try:
            if not check(contract):
                return name
        except (KeyError, TypeError, ValueError):
            return name
    return None


def on_contract(ch, method, _props, body):
    with CHECK_SECONDS.time():
        try:
            contract = json.loads(body)
            if not isinstance(contract, dict):
                raise ValueError("not a JSON object")
        except ValueError:  # includes JSONDecodeError and UnicodeDecodeError
            UNREADABLE.inc()
            log.error("unreadable message on %s, dead-lettered", method.routing_key)
            ch.basic_nack(method.delivery_tag, requeue=False)  # native dead-lettering
            return

        pays, source = str(contract.get("pays", "??")), str(contract.get("source", "??"))
        headers = {"x-source": source, "x-pays": pays}
        rule = first_failed_rule(contract)
        if rule is None:
            publish(ch, EXCHANGE, f"valide.{pays}", body, headers)
            VALID.labels(pays, source).inc()
        else:
            headers["x-regle"] = rule
            publish(ch, DLX, f"rejet.{rule}", body, headers)
            REJECTED.labels(pays, source, rule).inc()
            log.info("contract %s from %s/%s rejected: %s", contract.get("id"), source, pays, rule)
        ch.basic_ack(method.delivery_tag)  # ack only once the outcome is confirmed


def run_controleur(ch):
    ch.basic_qos(prefetch_count=20)
    ch.basic_consume(Q_IN, on_contract)
    ch.start_consuming()


# --------------------------------------------------------------------------- si-central
def on_valid(ch, method, _props, body):
    contract = json.loads(body)
    time.sleep(random.uniform(0.01, 0.05))  # simulated integration work
    INTEGRATED.labels(contract["pays"]).inc()
    ch.basic_ack(method.delivery_tag)


def run_si_central(ch):
    ch.basic_qos(prefetch_count=20)
    ch.basic_consume(Q_OK, on_valid)
    ch.start_consuming()


ROLES = {"producteur": run_producteur, "controleur": run_controleur, "si-central": run_si_central}


def main():
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    if ROLE not in ROLES:
        sys.exit(f"unknown ROLE {ROLE!r}, expected one of {sorted(ROLES)}")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    start_http_server(METRICS_PORT)
    while True:
        conn, ch = connect()
        try:
            ROLES[ROLE](ch)
        except pika.exceptions.AMQPError as exc:
            log.warning("connection lost (%r), reconnecting in 5s", exc)
            time.sleep(5)
        finally:
            if conn.is_open:
                try:
                    conn.close()
                except pika.exceptions.AMQPError:
                    pass


if __name__ == "__main__":
    main()
