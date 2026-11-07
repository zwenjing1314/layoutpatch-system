/** One generation for all private state: late responses cannot cross identities. */
export class RequestGeneration {
  private value = 0;
  private pending = new Set<() => void>();
  reset() {
    this.value += 1;
    const callbacks = [...this.pending]; this.pending.clear();
    callbacks.forEach((cancel) => cancel());
    return this.value;
  }
  current() { return this.value; }
  accepts(value: number) { return value === this.value; }
  track(cancel: () => void) {
    this.pending.add(cancel);
    return () => { this.pending.delete(cancel); };
  }
}

export function privatePreviewPath(value: string) {
  if (!/^\/pages\/[0-9a-f-]{36}\/image\?preview=[0-9a-f]{64}$/.test(value)) throw new Error("Invalid preview response");
  return `/api${value}`;
}
