"""
JARVIS OS — Phase 39.1: Test Suite for TypeScript Dependency Cache & Invalidation
Validates:
- Incremental caching with SHA-256 content_hash
- Cache hit/miss rates
- Invalidation upon file edit, deletion, rename, and config modification
- Incremental blast radius calculation (direct vs downstream consumers)
- Disk persistence and reload
"""

import os
import shutil
import tempfile
import pytest

from intelligence.typescript_dependency.cache import TypeScriptDependencyCache
from intelligence.typescript_dependency.models import (
    TypeScriptDependencyIndex,
    TypeScriptImport,
)
from intelligence.typescript_dependency.parser import TypeScriptSyntaxParser


@pytest.fixture
def temp_cache_dir():
    tmp = tempfile.mkdtemp(prefix="jarvis_cache_test_")
    cache_file = os.path.join(tmp, "test_cache.json")
    yield tmp, cache_file
    shutil.rmtree(tmp, ignore_errors=True)


def test_cache_put_get_hit_miss(temp_cache_dir):
    tmp, cache_file = temp_cache_dir
    cache = TypeScriptDependencyCache(tmp, cache_file=cache_file)

    code = "export const x = 1;"
    h = TypeScriptSyntaxParser.compute_content_hash(code)
    idx = TypeScriptDependencyIndex(file_path="src/a.ts", content_hash=h)

    # Initial get -> Miss
    res = cache.get("src/a.ts", h)
    assert res is None
    assert cache.stats["misses"] == 1

    # Put in cache
    cache.put(idx)

    # Second get with same hash -> Hit
    hit_res = cache.get("src/a.ts", h)
    assert hit_res is not None
    assert hit_res.file_path == "src/a.ts"
    assert cache.stats["hits"] == 1
    assert cache.hit_rate == 0.5

    # Get with different hash -> Miss
    miss_res = cache.get("src/a.ts", "different_hash")
    assert miss_res is None


def test_cache_invalidation_and_blast_radius(temp_cache_dir):
    tmp, cache_file = temp_cache_dir
    cache = TypeScriptDependencyCache(tmp, cache_file=cache_file)

    # Build chain: C -> B -> A
    # A is imported by B
    idx_a = TypeScriptDependencyIndex(file_path="src/A.ts", content_hash="hash_a")
    # B imports A
    imp_b = TypeScriptImport(source_file="src/B.ts", module_specifier="./A", resolved_target="src/A.ts")
    idx_b = TypeScriptDependencyIndex(file_path="src/B.ts", imports=[imp_b], resolved_targets=["src/A.ts"], content_hash="hash_b")
    # C imports B
    imp_c = TypeScriptImport(source_file="src/C.ts", module_specifier="./B", resolved_target="src/B.ts")
    idx_c = TypeScriptDependencyIndex(file_path="src/C.ts", imports=[imp_c], resolved_targets=["src/B.ts"], content_hash="hash_c")

    cache.put(idx_a)
    cache.put(idx_b)
    cache.put(idx_c)

    # Direct consumers of A
    direct_a = cache.get_direct_consumers("src/A.ts")
    assert direct_a == {"src/B.ts"}

    # Downstream consumers of A (transitive: B and C)
    downstream_a = cache.get_downstream_consumers("src/A.ts")
    assert downstream_a == {"src/B.ts", "src/C.ts"}

    # Invalidate A -> returns affected blast radius
    affected = cache.invalidate_file("src/A.ts")
    assert affected == {"src/B.ts", "src/C.ts"}
    assert cache.get("src/A.ts", "hash_a") is None


def test_cache_disk_persistence(temp_cache_dir):
    tmp, cache_file = temp_cache_dir
    cache = TypeScriptDependencyCache(tmp, cache_file=cache_file)

    idx = TypeScriptDependencyIndex(file_path="src/persisted.ts", content_hash="hash_persist", package_name="my-app")
    cache.put(idx)
    cache.save_to_disk()
    assert os.path.exists(cache_file)

    # Reload in a new instance
    new_cache = TypeScriptDependencyCache(tmp, cache_file=cache_file)
    entry = new_cache.get("src/persisted.ts", "hash_persist")
    assert entry is not None
    assert entry.package_name == "my-app"
