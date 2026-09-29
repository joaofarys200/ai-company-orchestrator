// Polyfills for Electron 31 (Chromium 126) compatibility
if (typeof (Map.prototype as any).getOrInsertComputed !== 'function') {
  (Map.prototype as any).getOrInsertComputed = function (key: any, callbackFn: (k: any) => any) {
    if (this.has(key)) {
      return this.get(key);
    }
    const value = callbackFn(key);
    this.set(key, value);
    return value;
  };
}
if (typeof (Map.prototype as any).getOrInsert !== 'function') {
  (Map.prototype as any).getOrInsert = function (key: any, defaultValue: any) {
    if (this.has(key)) {
      return this.get(key);
    }
    this.set(key, defaultValue);
    return defaultValue;
  };
}
if (typeof (WeakMap.prototype as any).getOrInsertComputed !== 'function') {
  (WeakMap.prototype as any).getOrInsertComputed = function (key: any, callbackFn: (k: any) => any) {
    if (this.has(key)) {
      return this.get(key);
    }
    const value = callbackFn(key);
    this.set(key, value);
    return value;
  };
}
if (typeof (WeakMap.prototype as any).getOrInsert !== 'function') {
  (WeakMap.prototype as any).getOrInsert = function (key: any, defaultValue: any) {
    if (this.has(key)) {
      return this.get(key);
    }
    this.set(key, defaultValue);
    return defaultValue;
  };
}

if (typeof (Math as any).sumPrecise !== 'function') {
  (Math as any).sumPrecise = function (items: any) {
    let sum = 0;
    for (const item of items) {
      sum += Number(item) || 0;
    }
    return sum;
  };
}

if (typeof (Uint8Array.prototype as any).toHex !== 'function') {
  (Uint8Array.prototype as any).toHex = function () {
    let hex = '';
    for (let i = 0; i < this.length; i++) {
      hex += this[i].toString(16).padStart(2, '0');
    }
    return hex;
  };
}
if (typeof (Uint8Array as any).fromHex !== 'function') {
  (Uint8Array as any).fromHex = function (hex: string) {
    const len = Math.floor(hex.length / 2);
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = parseInt(hex.substring(i * 2, i * 2 + 2), 16);
    }
    return bytes;
  };
}
if (typeof (Uint8Array.prototype as any).toBase64 !== 'function') {
  (Uint8Array.prototype as any).toBase64 = function () {
    let binary = '';
    for (let i = 0; i < this.length; i++) {
      binary += String.fromCharCode(this[i]);
    }
    return btoa(binary);
  };
}
if (typeof (Uint8Array as any).fromBase64 !== 'function') {
  (Uint8Array as any).fromBase64 = function (base64: string) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
  };
}

if (typeof (Promise as any).try !== 'function') {
  (Promise as any).try = function (fn: any, ...args: any[]) {
    return new Promise((resolve) => resolve(fn(...args)));
  };
}
if (typeof (Promise as any).withResolvers !== 'function') {
  (Promise as any).withResolvers = function () {
    let resolve: any, reject: any;
    const promise = new Promise((res, rej) => {
      resolve = res;
      reject = rej;
    });
    return { promise, resolve, reject };
  };
}


import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { WebSocketProvider } from './context/WebSocketContext.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <WebSocketProvider>
      <App />
    </WebSocketProvider>
  </StrictMode>,
)
