/**
 * RetailFlow AI — Shared API Response Wrapper Type
 *
 * All backend endpoints return:
 *   { success: true, data: T, message: string }
 *   { success: false, data: null, message: string }
 */
export interface APIResponse<T> {
  success: boolean;
  data: T;
  message: string;
}

/** Pydantic validation error detail shape */
export interface APIErrorDetail {
  code: string;
  message: string;
}

/** Pagination metadata returned by list endpoints */
export interface PaginationMeta {
  total: number;
  page: number;
  limit: number;
  pages: number;
}
