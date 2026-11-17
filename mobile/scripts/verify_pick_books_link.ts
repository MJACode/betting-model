/**
 * The Discord landing page opens signalbase://pick/<id>. The parser accepts
 * that shape and refuses a sportsbook URL, a query-only URL, and a zero id.
 */
import { parsePickBooksUrl, pickBooksUrl } from '../src/lib/pickBooksLink';

function check(name: string, ok: boolean, detail = ''): void {
  if (!ok) {
    console.error('FAIL', name, detail);
    process.exitCode = 1;
  }
}

check('round trip', parsePickBooksUrl(pickBooksUrl(48211)) === 48211);
check('trailing slash', parsePickBooksUrl('signalbase://pick/48211/') === 48211);
check('query kept off the id', parsePickBooksUrl('signalbase://pick/48211?x=1') === 48211);
check('https is not the app route', parsePickBooksUrl('https://worker-production-229d.up.railway.app/pick/48211') === null);
check('a sportsbook url is not a pick', parsePickBooksUrl('https://sportsbook.fanduel.com/addToBetslip?marketId=1') === null);
check('zero is not a pick', parsePickBooksUrl('signalbase://pick/0') === null);
check('empty', parsePickBooksUrl('') === null);
check('null', parsePickBooksUrl(null) === null);

if (process.exitCode) {
  process.exit(process.exitCode);
}
console.log('verify_pick_books_link: ok');
