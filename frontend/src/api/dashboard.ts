import request from '@/utils/request'

export interface DashboardStats {
  total_projects: number
  total_tasks: number
  avg_progress: number
  status_distribution: {
    ongoing: number
    finished: number
    paused: number
  }
  dept_distribution: {
    dept_name: string
    count: number
  }[]
  nearing_deadline: {
    id: number
    project_name: string
    end_date: string
  }[]
  recent_projects: {
    id: number
    project_code: string
    project_name: string
    dept_name: string
    status: number
    task_count: number
    total_progress: number
  }[]
}

export function getDashboardStats(): Promise<DashboardStats> {
  return request.get('/dashboard/stats') as any
}
