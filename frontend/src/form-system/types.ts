export type PmsControlScalar = string | number | boolean | Date | null
export type PmsControlValue = PmsControlScalar | PmsControlScalar[] | undefined
export type PmsControlSize = 'compact' | 'regular'
export type PmsControlVariant = 'field' | 'binary'

export interface PmsOption {
  value: string | number | boolean
  label: string
  disabled?: boolean
}

export interface PmsControlStateProps {
  size?: PmsControlSize
  variant?: PmsControlVariant
  disabled?: boolean
  readonly?: boolean
  loading?: boolean
  error?: string
  ariaLabel?: string
}
