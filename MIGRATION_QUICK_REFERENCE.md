# Blacksmith Multi-Platform Migration - Quick Reference

## What Changed?

### Before vs After

| Aspect | Before | After |
|--------|--------|-------|
| **Build Strategy** | 3 jobs, multi-platform per job | 6 jobs, one platform per job |
| **ARM Builds** | QEMU emulation on x86 | Native ARM64 runners |
| **Docker Action** | Custom Python script | Blacksmith official action |
| **Cache Management** | Manual cache-from/cache-to | Automatic via Blacksmith |
| **Manifest Creation** | Built-in multi-platform | Explicit manifest merge |
| **Parallelization** | 3 variants sequential | 6 builds fully parallel |
| **Expected Speed** | Baseline | 5-10x faster |

## Image Tags Quick Reference

### For End Users (Multi-Arch Manifests)
```bash
# Recommended: Use these tags (auto-select architecture)
docker pull ghcr.io/openhands/agent-server:<SHA>-python
docker pull ghcr.io/openhands/agent-server:<SHA>-java
docker pull ghcr.io/openhands/agent-server:<SHA>-golang

# Main branch also has:
docker pull ghcr.io/openhands/agent-server:latest-python
```

### For Specific Architecture (If Needed)
```bash
# Individual architecture tags
docker pull ghcr.io/openhands/agent-server:<SHA>-python-amd64
docker pull ghcr.io/openhands/agent-server:<SHA>-python-arm64
```

## Workflow Jobs

```
┌─────────────────────────────────────────────────────────┐
│  build-and-push-image (6 parallel jobs)                │
├─────────────────────────────────────────────────────────┤
│  ├─ python-amd64  → tag: SHA-python-amd64              │
│  ├─ python-arm64  → tag: SHA-python-arm64              │
│  ├─ java-amd64    → tag: SHA-java-amd64                │
│  ├─ java-arm64    → tag: SHA-java-arm64                │
│  ├─ golang-amd64  → tag: SHA-golang-amd64              │
│  └─ golang-arm64  → tag: SHA-golang-arm64              │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  merge-manifests (3 parallel jobs)                     │
├─────────────────────────────────────────────────────────┤
│  ├─ python   → manifest: SHA-python (amd64+arm64)      │
│  ├─ java     → manifest: SHA-java (amd64+arm64)        │
│  └─ golang   → manifest: SHA-golang (amd64+arm64)      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  consolidate-build-info                                │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  update-pr-description                                 │
└─────────────────────────────────────────────────────────┘
```

## Key Actions Used

### 1. Setup Docker Builder (Blacksmith)
```yaml
- uses: useblacksmith/setup-docker-builder@v1
```
**Purpose:** Configures buildx with Blacksmith's NVMe-backed cache

### 2. Build & Push (Blacksmith)
```yaml
- uses: useblacksmith/build-push-action@v2
  with:
    platforms: linux/amd64  # Single platform per job
    push: true
    tags: ${{ steps.prep.outputs.tags }}
```
**Purpose:** Builds image using cached layers, commits cache updates

### 3. Manifest Merge (Docker CLI)
```bash
docker manifest create image:tag image:tag-amd64 image:tag-arm64
docker manifest annotate --arch amd64
docker manifest annotate --arch arm64
docker manifest push image:tag
```
**Purpose:** Combines architecture-specific images into multi-arch manifest

## Runner Assignments

| Architecture | Runner Label | Hardware |
|--------------|-------------|----------|
| **amd64** | `blacksmith-8vcpu-ubuntu-2404` | Native x86_64 |
| **arm64** | `blacksmith-8vcpu-ubuntu-2404-arm` | Native ARM64 |

## Performance Expectations

### First Run (Cold Cache)
- **Time:** Similar to before (~10-15 min per variant)
- **Benefit:** Native ARM builds (no QEMU)
- **Cache:** Being populated

### Second Run Onward (Warm Cache)
- **Time:** 2-10x faster (only rebuild changed layers)
- **Benefit:** Cache hits + native builds
- **Cache:** Reused from previous runs

### Typical Speedup Timeline
```
Run 1 (cold):     ~12 min per variant → ~12 min total (parallel)
Run 2 (warm):     ~3-5 min per variant → ~5 min total
Run 3+ (stable):  ~2-3 min per variant → ~3 min total
```

## Cost Structure

### Compute
- **Billing:** Standard Blacksmith runner rates
- **Savings:** Less time = lower cost
- **No extra charges** for caching feature

### Storage
- **Rate:** $0.50/GB/month
- **Billing:** Hourly snapshots
- **Typical size:** 5-20 GB depending on base images
- **Monthly cost:** ~$2.50-$10

## Verification Steps

### 1. Check Build Logs
```
✓ Look for: "cache hit" messages
✓ Verify: amd64 jobs on blacksmith-8vcpu-ubuntu-2404
✓ Verify: arm64 jobs on blacksmith-8vcpu-ubuntu-2404-arm
```

### 2. Inspect Multi-Arch Manifest
```bash
docker manifest inspect ghcr.io/openhands/agent-server:<SHA>-python

# Should show both:
# - linux/amd64
# - linux/arm64
```

### 3. Test Auto-Architecture Selection
```bash
# On amd64 machine
docker pull ghcr.io/openhands/agent-server:<SHA>-python
docker inspect --format='{{.Architecture}}' <image-id>
# Should show: amd64

# On arm64 machine (Mac M1/M2, ARM server)
docker pull ghcr.io/openhands/agent-server:<SHA>-python
docker inspect --format='{{.Architecture}}' <image-id>
# Should show: arm64
```

## Troubleshooting Quick Guide

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| Slow builds on 1st run | Expected (cold cache) | Wait for 2nd run |
| ARM still slow | Wrong runner | Check job ran on `-arm` runner |
| Manifest merge fails | Tag not found | Verify both arch tags pushed |
| No cache hits | First time / cache cleared | Normal for first run |
| High storage cost | Large base images | Monitor dashboard, optimize if needed |

## Monitoring

### Blacksmith Dashboard
1. Login to Blacksmith
2. Navigate to "Usage & Billing"
3. Check:
   - Docker layer cache size
   - Build analytics
   - Cache hit rates

### GitHub Actions
1. Open workflow run
2. Check job execution times
3. Look for cache-related messages in logs
4. Verify runner assignments in job metadata

## Common Commands

### Pull Multi-Arch Image
```bash
docker pull ghcr.io/openhands/agent-server:<SHA>-python
```

### Inspect Manifest
```bash
docker manifest inspect ghcr.io/openhands/agent-server:<SHA>-python
```

### Pull Specific Architecture
```bash
docker pull --platform linux/amd64 ghcr.io/openhands/agent-server:<SHA>-python
docker pull --platform linux/arm64 ghcr.io/openhands/agent-server:<SHA>-python
```

### Run on Specific Platform (for testing)
```bash
docker run --platform linux/amd64 -it --rm \
  ghcr.io/openhands/agent-server:<SHA>-python
```

## Key Benefits

1. **⚡ Faster Builds**
   - 2-40x with layer caching
   - 5-10x for ARM (native vs QEMU)
   - Overall: 5-10x pipeline speedup

2. **💰 Cost Savings**
   - Less compute time
   - Predictable storage costs
   - Better resource utilization

3. **🌐 Better Platform Support**
   - True multi-arch images
   - Native performance on all platforms
   - Auto-select correct architecture

4. **🔧 Easier Maintenance**
   - Official Blacksmith actions
   - Automatic cache management
   - Better observability

## Files Modified

- `.github/workflows/server.yml` - Complete workflow refactor
- Matrix strategy updated (3 jobs → 6 jobs)
- Added `merge-manifests` job
- Updated consolidation and PR description logic

## Next Actions

1. ✅ Push changes to branch
2. ✅ Open PR
3. ⏳ Monitor first build (cold cache)
4. ⏳ Monitor second build (warm cache)
5. ⏳ Verify multi-arch manifests
6. ⏳ Check Blacksmith dashboard
7. ⏳ Document final performance numbers

## Support

- **Blacksmith Docs:** https://docs.blacksmith.sh/blacksmith-caching/docker-builds
- **Issues:** Check GitHub Actions logs first
- **Cache Issues:** Blacksmith dashboard → Usage & Billing
- **Questions:** Reference BLACKSMITH_MULTIPLATFORM_MIGRATION.md for details

---

**Quick Start:** Just merge the PR! The workflow will automatically:
1. Build all variants on native hardware (6 parallel jobs)
2. Create multi-arch manifests
3. Update PR description with image info
4. Cache layers for next run

**That's it! 🎉**
