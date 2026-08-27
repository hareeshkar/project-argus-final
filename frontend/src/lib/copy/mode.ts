export type CopyMode = 'simple' | 'experience'

export const COPY_MODE_STORAGE_KEY = 'argus_copy_mode'
export const DEFAULT_COPY_MODE: CopyMode = 'simple'

export function parseCopyMode(value: string | null | undefined): CopyMode {
  if (value === 'experience') return 'experience'
  return DEFAULT_COPY_MODE
}

export function loadCopyMode(): CopyMode {
  try {
    return parseCopyMode(localStorage.getItem(COPY_MODE_STORAGE_KEY))
  } catch {
    return DEFAULT_COPY_MODE
  }
}

export function saveCopyMode(mode: CopyMode): void {
  try {
    localStorage.setItem(COPY_MODE_STORAGE_KEY, mode)
  } catch {
    // ignore storage failures
  }
}
