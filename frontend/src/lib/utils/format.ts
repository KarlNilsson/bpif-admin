// All currency and date presentation goes through these functions, so the
// app is consistent. Dates are shown in Swedish time whatever time zone the
// browser is in, since the club and its fees are in Sweden.
//
// `Intl` puts a non-breaking space between the amount and "kr"; that's
// intended.

const LOCALE = 'sv-SE';
const TIME_ZONE = 'Europe/Stockholm';

const wholeKronor = new Intl.NumberFormat(LOCALE, {
	style: 'currency',
	currency: 'SEK',
	minimumFractionDigits: 0,
	maximumFractionDigits: 0
});

const kronorAndOre = new Intl.NumberFormat(LOCALE, {
	style: 'currency',
	currency: 'SEK',
	minimumFractionDigits: 2,
	maximumFractionDigits: 2
});

const date = new Intl.DateTimeFormat(LOCALE, { dateStyle: 'short', timeZone: TIME_ZONE });

const dateTime = new Intl.DateTimeFormat(LOCALE, {
	dateStyle: 'short',
	timeStyle: 'short',
	timeZone: TIME_ZONE
});

/** Formats an amount in öre: 30000 -> '300 kr', 30050 -> '300,50 kr'. */
export function formatCurrency(ore: number): string {
	const formatter = ore % 100 === 0 ? wholeKronor : kronorAndOre;
	return formatter.format(ore / 100);
}

/** Formats a 10-digit Swish number: '1231234567' -> '123 123 45 67'. */
export function formatSwishNumber(number: string): string {
	return number.replace(/^(\d{3})(\d{3})(\d{2})(\d{2})$/, '$1 $2 $3 $4');
}

/** Formats a date (or ISO string) as '2026-11-02'. */
export function formatDate(value: string | Date): string {
	return date.format(new Date(value));
}

/** Formats a date and time (or ISO string) as '2026-11-02 14:30'. */
export function formatDateTime(value: string | Date): string {
	return dateTime.format(new Date(value));
}
