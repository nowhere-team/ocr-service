import { decimal as pgDecimal, integer, timestamp } from 'drizzle-orm/pg-core'

export const timestamptz = (column: string) => timestamp(column, { withTimezone: true })

export const money = (column: string) => integer(column)

export const decimal = (column: string, precision: number, scale: number) => pgDecimal(column, { precision, scale })
