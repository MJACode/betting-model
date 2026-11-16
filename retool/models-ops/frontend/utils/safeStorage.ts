// localStorage that never throws: private windows and locked-down browsers can
// refuse access, and the dashboard must keep working without it.

export function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

export function writeStorage(key: string, value: string | null): void {
  try {
    if (value == null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch {
    // ignore: the preference just will not be remembered
  }
}
