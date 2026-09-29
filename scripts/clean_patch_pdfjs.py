CLEAN_POLYFILL = """// Polyfill Map.prototype.getOrInsertComputed and getOrInsert
if (typeof Map !== "undefined" && typeof Map.prototype.getOrInsertComputed !== "function") {
  Map.prototype.getOrInsertComputed = function (key, callbackFn) {
    if (this.has(key)) return this.get(key);
    var value = callbackFn(key);
    this.set(key, value);
    return value;
  };
}
if (typeof Map !== "undefined" && typeof Map.prototype.getOrInsert !== "function") {
  Map.prototype.getOrInsert = function (key, defaultValue) {
    if (this.has(key)) return this.get(key);
    this.set(key, defaultValue);
    return defaultValue;
  };
}
if (typeof WeakMap !== "undefined" && typeof WeakMap.prototype.getOrInsertComputed !== "function") {
  WeakMap.prototype.getOrInsertComputed = function (key, callbackFn) {
    if (this.has(key)) return this.get(key);
    var value = callbackFn(key);
    this.set(key, value);
    return value;
  };
}
if (typeof WeakMap !== "undefined" && typeof WeakMap.prototype.getOrInsert !== "function") {
  WeakMap.prototype.getOrInsert = function (key, defaultValue) {
    if (this.has(key)) return this.get(key);
    this.set(key, defaultValue);
    return defaultValue;
  };
}

// Polyfill Math.sumPrecise
if (typeof Math !== "undefined" && typeof Math.sumPrecise !== "function") {
  Math.sumPrecise = function (items) {
    var sum = 0;
    if (items) {
      for (var val of items) {
        sum += Number(val) || 0;
      }
    }
    return sum;
  };
}

// Polyfill Uint8Array.prototype.toHex
if (typeof Uint8Array !== "undefined" && typeof Uint8Array.prototype.toHex !== "function") {
  Uint8Array.prototype.toHex = function () {
    var hex = "";
    for (var i = 0; i < this.length; i++) {
      hex += this[i].toString(16).padStart(2, "0");
    }
    return hex;
  };
}

// Polyfill Uint8Array.fromHex
if (typeof Uint8Array !== "undefined" && typeof Uint8Array.fromHex !== "function") {
  Uint8Array.fromHex = function (hex) {
    var len = Math.floor(hex.length / 2);
    var bytes = new Uint8Array(len);
    for (var i = 0; i < len; i++) {
      bytes[i] = parseInt(hex.substring(i * 2, i * 2 + 2), 16);
    }
    return bytes;
  };
}

// Polyfill Uint8Array.prototype.toBase64
if (typeof Uint8Array !== "undefined" && typeof Uint8Array.prototype.toBase64 !== "function") {
  Uint8Array.prototype.toBase64 = function () {
    var binary = "";
    for (var i = 0; i < this.length; i++) {
      binary += String.fromCharCode(this[i]);
    }
    return btoa(binary);
  };
}

// Polyfill Uint8Array.fromBase64
if (typeof Uint8Array !== "undefined" && typeof Uint8Array.fromBase64 !== "function") {
  Uint8Array.fromBase64 = function (base64) {
    var binary = atob(base64);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
  };
}

// Polyfill Promise.try
if (typeof Promise !== "undefined" && typeof Promise.try !== "function") {
  Promise.try = function (fn) {
    var args = Array.prototype.slice.call(arguments, 1);
    return new Promise(function (resolve) {
      resolve(fn.apply(null, args));
    });
  };
}

// Polyfill Promise.withResolvers
if (typeof Promise !== "undefined" && typeof Promise.withResolvers !== "function") {
  Promise.withResolvers = function () {
    var resolve, reject;
    var promise = new Promise(function (res, rej) {
      resolve = res;
      reject = rej;
    });
    return { promise: promise, resolve: resolve, reject: reject };
  };
}
"""

import os

files_to_patch = [
    "frontend/public/pdf.worker.min.mjs",
    "frontend/public/pdf.worker.mjs",
    "frontend/dist/pdf.worker.min.mjs",
    "frontend/dist/pdf.worker.mjs",
    "frontend/node_modules/pdfjs-dist/build/pdf.worker.min.mjs",
    "frontend/node_modules/pdfjs-dist/build/pdf.worker.mjs",
    "frontend/node_modules/pdfjs-dist/build/pdf.mjs",
    "frontend/node_modules/pdfjs-dist/build/pdf.min.mjs",
]

for fp in files_to_patch:
    if os.path.exists(fp):
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Remove any previous polyfill prepends
        while content.startswith("// Polyfill") or content.startswith("if (typeof") or content.startswith("if(typeof"):
            # find first occurrence of original comment or code
            idx = content.find("/**\n * @licstart")
            if idx == -1:
                idx = content.find("/* Copyright")
            if idx == -1:
                idx = content.find("class ")
            if idx == -1:
                idx = content.find("const ")
            if idx != -1:
                content = content[idx:]
            else:
                break
        
        with open(fp, "w", encoding="utf-8") as f:
            f.write(CLEAN_POLYFILL + "\n" + content)
        print(f"Cleanly patched with full polyfills: {fp}")
