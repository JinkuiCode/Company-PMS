declare module 'echarts/core' {
  export function use(extensions: unknown[]): void
}

declare module 'echarts/charts' {
  export const PieChart: unknown
  export const BarChart: unknown
}

declare module 'echarts/components' {
  export const TitleComponent: unknown
  export const TooltipComponent: unknown
  export const LegendComponent: unknown
  export const GridComponent: unknown
}

declare module 'echarts/renderers' {
  export const CanvasRenderer: unknown
}
