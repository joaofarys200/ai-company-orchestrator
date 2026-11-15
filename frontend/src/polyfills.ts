// Runtime polyfills loaded before application and worker modules (CSP-safe replacement for inline HTML scripts)
if (typeof (Map.prototype as unknown as { getOrInsertComputed?: unknown }).getOrInsertComputed !== 'function') {
  (Map.prototype as unknown as Record<string, unknown>).getOrInsertComputed = function <K, V>(
    this: Map<K, V>,
    key: K,
    callbackFn: (k: K) => V,
  ): V {
    if (this.has(key)) {
      return this.get(key) as V;
    }
    const value = callbackFn(key);
    this.set(key, value);
    return value;
  };
}

if (typeof (Map.prototype as unknown as { getOrInsert?: unknown }).getOrInsert !== 'function') {
  (Map.prototype as unknown as Record<string, unknown>).getOrInsert = function <K, V>(
    this: Map<K, V>,
    key: K,
    defaultValue: V,
  ): V {
    if (this.has(key)) {
      return this.get(key) as V;
    }
    this.set(key, defaultValue);
    return defaultValue;
  };
}

if (typeof (WeakMap.prototype as unknown as { getOrInsertComputed?: unknown }).getOrInsertComputed !== 'function') {
  (WeakMap.prototype as unknown as Record<string, unknown>).getOrInsertComputed = function <K extends WeakKey, V>(
    this: WeakMap<K, V>,
    key: K,
    callbackFn: (k: K) => V,
  ): V {
    if (this.has(key)) {
      return this.get(key) as V;
    }
    const value = callbackFn(key);
    this.set(key, value);
    return value;
  };
}

if (typeof (WeakMap.prototype as unknown as { getOrInsert?: unknown }).getOrInsert !== 'function') {
  (WeakMap.prototype as unknown as Record<string, unknown>).getOrInsert = function <K extends WeakKey, V>(
    this: WeakMap<K, V>,
    key: K,
    defaultValue: V,
  ): V {
    if (this.has(key)) {
      return this.get(key) as V;
    }
    this.set(key, defaultValue);
    return defaultValue;
  };
}

if (typeof (Math as unknown as { sumPrecise?: unknown }).sumPrecise !== 'function') {
  (Math as unknown as Record<string, unknown>).sumPrecise = function (items: Iterable<number>): number {
    let sum = 0;
    for (const item of items) {
      sum += Number(item) || 0;
    }
    return sum;
  };
}

if (typeof (Uint8Array.prototype as unknown as { toHex?: unknown }).toHex !== 'function') {
  (Uint8Array.prototype as unknown as Record<string, unknown>).toHex = function (this: Uint8Array): string {
    let hex = '';
    for (let i = 0; i < this.length; i++) {
      hex += this[i].toString(16).padStart(2, '0');
    }
    return hex;
  };
}

if (typeof (Uint8Array as unknown as { fromHex?: unknown }).fromHex !== 'function') {
  (Uint8Array as unknown as Record<string, unknown>).fromHex = function (hex: string): Uint8Array {
    const len = Math.floor(hex.length / 2);
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = parseInt(hex.substring(i * 2, i * 2 + 2), 16);
    }
    return bytes;
  };
}

if (typeof (Uint8Array.prototype as unknown as { toBase64?: unknown }).toBase64 !== 'function') {
  (Uint8Array.prototype as unknown as Record<string, unknown>).toBase64 = function (this: Uint8Array): string {
    let binary = '';
    for (let i = 0; i < this.length; i++) {
      binary += String.fromCharCode(this[i]);
    }
    return btoa(binary);
  };
}

if (typeof (Uint8Array as unknown as { fromBase64?: unknown }).fromBase64 !== 'function') {
  (Uint8Array as unknown as Record<string, unknown>).fromBase64 = function (base64: string): Uint8Array {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
  };
}

if (typeof (Promise as unknown as { try?: unknown }).try !== 'function') {
  (Promise as unknown as Record<string, unknown>).try = function <T, A extends unknown[]>(
    fn: (...args: A) => T | PromiseLike<T>,
    ...args: A
  ): Promise<T> {
    return new Promise<T>((resolve) => resolve(fn(...args)));
  };
}

if (typeof (Promise as unknown as { withResolvers?: unknown }).withResolvers !== 'function') {
  (Promise as unknown as Record<string, unknown>).withResolvers = function <T>() {
    let resolve!: (value: T | PromiseLike<T>) => void;
    let reject!: (reason?: unknown) => void;
    const promise = new Promise<T>((res, rej) => {
      resolve = res;
      reject = rej;
    });
    return { promise, resolve, reject };
  };
}

