// Readarr monitors the most popular edition of each book, which is usually the
// English one, and has no setting to prefer an edition language. This job makes
// the preferred-language edition the monitored one whenever a book has one, so
// searches use the French title. Books that already have files are left alone.
// With UNMONITOR_WITHOUT_PREFERRED=true, books that have no edition in the
// preferred language are unmonitored so they are not grabbed in another one.
const UNMONITOR = process.env.UNMONITOR_WITHOUT_PREFERRED === "true";
const URL_BASE = (process.env.READARR_URL || "http://readarr.downloads.svc.cluster.local:8787") + "/api/v1/";
const API_KEY = process.env.READARR_API_KEY;
const LANGUAGE = process.env.PREFERRED_LANGUAGE || "fra";

async function api(method, path, body) {
  const res = await fetch(URL_BASE + path, {
    method,
    headers: { "X-Api-Key": API_KEY, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(method + " " + path + " -> HTTP " + res.status);
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

const votes = (edition) => (edition.ratings && edition.ratings.votes) || 0;

async function main() {
  if (!API_KEY) throw new Error("READARR_API_KEY is not set");
  const authors = new Map((await api("GET", "author")).map((a) => [a.id, a.authorName]));
  const books = await api("GET", "book");
  let switched = 0, failed = 0;
  const toUnmonitor = [];

  for (const book of books) {
    if (book.statistics && book.statistics.bookFileCount > 0) continue;
    try {
      const editions = await api("GET", "edition?bookId=" + book.id);
      const current = editions.find((e) => e.monitored);
      if (current && current.language === LANGUAGE) continue;
      const target = editions.filter((e) => e.language === LANGUAGE).sort((x, y) => votes(y) - votes(x))[0];
      if (!target) {
        if (UNMONITOR && book.monitored) toUnmonitor.push(book.id);
        continue;
      }

      const full = await api("GET", "book/" + book.id);
      full.editions = editions.map((e) => ({ ...e, monitored: e.id === target.id }));
      await api("PUT", "book/" + book.id, full);
      switched++;
      console.log("switched: " + (authors.get(book.authorId) || "?") + ' - "' + (current ? current.title : book.title) + '" -> "' + target.title + '"');
    } catch (err) {
      failed++;
      console.error("failed: book " + book.id + " (" + book.title + "): " + err.message);
    }
  }

  if (toUnmonitor.length > 0) {
    try {
      await api("PUT", "book/monitor", { bookIds: toUnmonitor, monitored: false });
    } catch (err) {
      failed++;
      console.error("failed: unmonitor " + toUnmonitor.length + " books: " + err.message);
    }
  }

  console.log("books: " + books.length + " | switched to " + LANGUAGE + ": " + switched + " | unmonitored (no " + LANGUAGE + " edition): " + toUnmonitor.length + " | failed: " + failed);
  if (failed > 0) process.exitCode = 1;
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
