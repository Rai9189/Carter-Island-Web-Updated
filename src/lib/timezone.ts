import moment from 'moment-timezone'

// Set default timezone ke Indonesia
const INDONESIA_TIMEZONE = 'Asia/Jakarta'

export class TimezoneUtil {
  static getRelativeTime(updatedAt: Date | string): string {
    return moment(updatedAt).tz(INDONESIA_TIMEZONE).fromNow()
  }
  static formatForDisplay(createdAt: Date | string): string {
    return moment(createdAt).tz(INDONESIA_TIMEZONE).format('DD MMM YYYY, HH:mm')
  }
  // Get current time in Indonesia timezone
  static now(): Date {
    return moment().tz(INDONESIA_TIMEZONE).toDate()
  }

  // Convert any date to Indonesia timezone
  static toIndonesia(date: Date | string): Date {
    return moment(date).tz(INDONESIA_TIMEZONE).toDate()
  }

  // Format date to Indonesian format
  static formatIndonesian(date: Date | string): string {
    return moment(date).tz(INDONESIA_TIMEZONE).format('DD-MM-YYYY HH:mm:ss')
  }

  // Get Indonesian timestamp string
  static getTimestamp(): string {
    return moment().tz(INDONESIA_TIMEZONE).format('YYYY-MM-DD HH:mm:ss')
  }

  // Add hours/days/months to current Indonesia time
  static addTime(amount: number, unit: 'hours' | 'days' | 'months'): Date {
    return moment().tz(INDONESIA_TIMEZONE).add(amount, unit).toDate()
  }

  // Check if date is today in Indonesia timezone
  static isToday(date: Date | string): boolean {
    const indonesianNow = moment().tz(INDONESIA_TIMEZONE)
    const checkDate = moment(date).tz(INDONESIA_TIMEZONE)
    return indonesianNow.isSame(checkDate, 'day')
  }
}