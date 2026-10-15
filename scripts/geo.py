# -*- coding: utf-8 -*-
# Legacy resource: not used by the active svg-redraw workflow; follow SKILL.md.
"""Shared geometry helpers for the illustration tracing pipeline."""
import math
import numpy as np

# ---------------------------------------------------------------- morphology
def _shift(a, dy, dx, fill):
    out = np.full_like(a, fill)
    ys = slice(max(0, dy), a.shape[0] + min(0, dy))
    yd = slice(max(0, -dy), a.shape[0] + min(0, -dy))
    xs = slice(max(0, dx), a.shape[1] + min(0, dx))
    xd = slice(max(0, -dx), a.shape[1] + min(0, -dx))
    out[yd, xd] = a[ys, xs]
    return out

def dilate(mask, r=1, conn=8):
    m = mask.copy()
    offs = [(-1,0),(1,0),(0,-1),(0,1)]
    if conn == 8:
        offs += [(-1,-1),(-1,1),(1,-1),(1,1)]
    for _ in range(r):
        acc = m.copy()
        for dy, dx in offs:
            acc |= _shift(m, dy, dx, False)
        m = acc
    return m

def erode(mask, r=1, conn=8):
    m = mask.copy()
    offs = [(-1,0),(1,0),(0,-1),(0,1)]
    if conn == 8:
        offs += [(-1,-1),(-1,1),(1,-1),(1,1)]
    for _ in range(r):
        acc = m.copy()
        for dy, dx in offs:
            acc &= _shift(m, dy, dx, False)
        m = acc
    return m

def gray_dilate(g, r=1):
    m = g.copy()
    for _ in range(r):
        acc = m.copy()
        for dy, dx in ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)):
            acc = np.maximum(acc, _shift(m, dy, dx, 0.0))
        m = acc
    return m

def gray_erode(g, r=1):
    m = g.copy()
    for _ in range(r):
        acc = m.copy()
        for dy, dx in ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)):
            acc = np.minimum(acc, _shift(m, dy, dx, 1e9))
        m = acc
    return m

# ---------------------------------------------------------------- filtering
def bilateral(arr, radius=2, ss=2.0, sr=20.0):
    """Edge preserving smoothing of an HxWx3 float image."""
    pad = radius
    P = np.pad(arr, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
    out = np.zeros_like(arr)
    wsum = np.zeros(arr.shape[:2] + (1,), np.float32)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            sh = P[pad + dy:pad + dy + arr.shape[0], pad + dx:pad + dx + arr.shape[1]]
            d2 = ((sh - arr) ** 2).sum(2)
            w = np.exp(-(dy * dy + dx * dx) / (2.0 * ss * ss) - d2 / (2.0 * sr * sr))[:, :, None]
            out += sh * w
            wsum += w
    return out / np.maximum(wsum, 1e-6)

def mode_filter(labels, K, iters=2, thresh=4):
    """Replace noisy label pixels by the majority label of their 3x3 neighbourhood."""
    H, W = labels.shape
    offs = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
    lab = labels.copy()
    for _ in range(iters):
        best = np.full((H, W), -1, np.int32)
        bestc = np.zeros((H, W), np.int32)
        for L in range(K):
            m = lab == L
            if not m.any():
                continue
            cnt = np.zeros((H, W), np.int32)
            for dy, dx in offs:
                cnt += _shift(m, dy, dx, False).astype(np.int32)
            upd = cnt > bestc
            best[upd] = L
            bestc[upd] = cnt[upd]
        noisy = bestc <= thresh
        lab[noisy] = best[noisy]
    return lab

# ---------------------------------------------------------------- components
def components(mask, minpx=1):
    h, w = mask.shape
    seen = np.zeros((h, w), bool)
    out = []
    for sy, sx in np.argwhere(mask):
        if seen[sy, sx]:
            continue
        st = [(sy, sx)]
        seen[sy, sx] = True
        cur = []
        while st:
            y, x = st.pop()
            cur.append((y, x))
            if y + 1 < h and mask[y+1, x] and not seen[y+1, x]:
                seen[y+1, x] = True; st.append((y+1, x))
            if y >= 1 and mask[y-1, x] and not seen[y-1, x]:
                seen[y-1, x] = True; st.append((y-1, x))
            if x + 1 < w and mask[y, x+1] and not seen[y, x+1]:
                seen[y, x+1] = True; st.append((y, x+1))
            if x >= 1 and mask[y, x-1] and not seen[y, x-1]:
                seen[y, x-1] = True; st.append((y, x-1))
        if len(cur) >= minpx:
            out.append(np.array(cur, np.int32))
    return out

# ---------------------------------------------------------------- tracing
_LUT = {
    1: [("L","B")], 2: [("B","R")], 3: [("L","R")], 4: [("R","T")],
    5: [("L","T"),("R","B")], 6: [("B","T")], 7: [("L","T")], 8: [("T","L")],
    9: [("T","B")], 10: [("T","R"),("L","B")], 11: [("T","R")], 12: [("R","L")],
    13: [("R","B")], 14: [("B","L")],
}

def marching_squares(mask):
    m = np.pad(mask.astype(np.uint8), 1)
    a = m[:-1, :-1]; b = m[:-1, 1:]; c = m[1:, 1:]; d = m[1:, :-1]
    code = a * 8 + b * 4 + c * 2 + d
    ys, xs = np.nonzero((code != 0) & (code != 15))
    segs = []
    pts_all = {}
    for y, x in zip(ys.tolist(), xs.tolist()):
        pts_all.clear()
        pts_all.update({"T": (x + 0.5, float(y)), "R": (float(x + 1), y + 0.5),
                        "B": (x + 0.5, float(y + 1)), "L": (float(x), y + 0.5)})
        for (p, q) in _LUT[int(code[y, x])]:
            segs.append((pts_all[p], pts_all[q]))
    return segs

def chain(segs):
    """Assemble marching-squares segments into closed loops.

    All segments come out of the LUT already oriented around the region, so we follow
    end->start.  Ambiguous cases and hashing collisions are repaired by continuing with
    the nearest unused segment; a loop that still cannot be closed is discarded.
    """
    from collections import defaultdict
    key = lambda p: (int(round(p[0] * 2)), int(round(p[1] * 2)))
    bystart = defaultdict(list)
    for i, (p, q) in enumerate(segs):
        bystart[key(p)].append(i)
    used = bytearray(len(segs))
    loops = []
    for i in range(len(segs)):
        if used[i]:
            continue
        cur = i
        loop = []
        ok = True
        while True:
            used[cur] = 1
            p, q = segs[cur]
            loop.append(p)
            cands = [j for j in bystart.get(key(q), ()) if not used[j]]
            if not cands:
                # repair: nearest unused segment start within 2.5 px
                best = None
                bd = 6.25
                for j in range(len(segs)):
                    if used[j]:
                        continue
                    s = segs[j][0]
                    dd = (s[0] - q[0]) ** 2 + (s[1] - q[1]) ** 2
                    if dd < bd:
                        bd = dd
                        best = j
                if best is None:
                    ok = False
                    break
                cands = [best]
            if len(cands) > 1:
                # keep the straightest continuation
                vx, vy = q[0] - p[0], q[1] - p[1]
                def turn(j):
                    w = segs[j]
                    wx, wy = w[1][0] - w[0][0], w[1][1] - w[0][1]
                    return -(vx * wx + vy * wy) / (math.hypot(vx, vy) * math.hypot(wx, wy) + 1e-9)
                cands.sort(key=turn)
            nxt = cands[0]
            cur = nxt
            if key(segs[cur][1]) == key(loop[0]):
                loop.append(segs[cur][1])
                break
        if ok and len(loop) >= 4:
            loops.append(loop)
    return loops

def rdp(pts, eps):
    n = len(pts)
    if n < 3:
        return pts
    pts = np.asarray(pts, np.float64)
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    st = [(0, n - 1)]
    while st:
        i, j = st.pop()
        if j <= i + 1:
            continue
        p = pts[i]; v = pts[j] - p
        L = math.hypot(v[0], v[1])
        seg = pts[i+1:j]
        if L < 1e-9:
            dist = np.hypot(seg[:, 0] - p[0], seg[:, 1] - p[1])
        else:
            dist = np.abs(v[0] * (seg[:, 1] - p[1]) - v[1] * (seg[:, 0] - p[0])) / L
        k = int(dist.argmax())
        if dist[k] > eps:
            keep[i + 1 + k] = True
            st.append((i, i + 1 + k))
            st.append((i + 1 + k, j))
    return pts[keep]

def smooth_pts(pts, closed, passes=1):
    P = np.asarray(pts, np.float64)
    if len(P) < 5 or passes <= 0:
        return P
    if closed:
        Q = np.vstack([P[-1], P, P[0], P[1]])
        for _ in range(passes):
            Q = np.vstack([Q[0], (Q[:-2] + 2 * Q[1:-1] + Q[2:]) / 4.0, Q[-1]])
        return Q[1:-1]
    Q = P.copy()
    for _ in range(passes):
        Q[1:-1] = (Q[:-2] + 2 * Q[1:-1] + Q[2:]) / 4.0
    return Q

def path_from_pts(pts, closed=True, r=1):
    """Catmull-Rom to cubic bezier path string."""
    P = [(round(float(x), r), round(float(y), r)) for x, y in pts]
    if closed:
        if len(P) < 3:
            return ""
        count = len(P)
        P = P + [P[0], P[1]]
    else:
        count = len(P) - 1
    n = len(P)
    if count < 1:
        return ""
    d = ["M%s %s" % P[0]]
    for i in range(count):
        p0 = P[i - 1] if i >= 1 else P[0]
        p1 = P[i]; p2 = P[i + 1]
        p3 = P[i + 2] if i + 2 < n else P[-1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        d.append("C%.1f %.1f %.1f %.1f %.1f %.1f" % (c1[0], c1[1], c2[0], c2[1], p2[0], p2[1]))
    if closed:
        d.append("Z")
    return "".join(d)

def path_from_pts_linear(pts, closed=True, r=1):
    """Polyline path (M/L/Z).

    A cardinal spline overshoots on 1-3 px wide ink strokes, which under the nonzero
    fill rule punches holes into the stroke - the polyline never leaves the mask.
    """
    P = []
    for x, y in pts:
        q = (round(float(x), r), round(float(y), r))
        if not P or q != P[-1]:
            P.append(q)
    if len(P) < 3:
        return ""
    if closed and P[0] == P[-1]:
        P.pop()
    if len(P) < 3:
        return ""
    d = ["M%s %s" % P[0]]
    prev = P[0]
    for q in P[1:]:
        dx = q[0] - prev[0]; dy = q[1] - prev[1]
        if dx == 0:
            d.append("V%s" % q[1])
        elif dy == 0:
            d.append("H%s" % q[0])
        else:
            d.append("L%s %s" % q)
        prev = q
    if closed:
        d.append("Z")
    return "".join(d)

def poly_area(pts):
    x = np.asarray(pts)[:, 0]; y = np.asarray(pts)[:, 1]
    return float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) * 0.5)

def boundary_loops(mask):
    """Exact pixel-corner boundary walk of a binary mask.

    Every foreground/background side becomes a directed unit edge whose interior lies on
    the left, so the edges always form closed loops; holes come out automatically with
    opposite winding.  Render the result with fill-rule="nonzero".
    """
    from collections import defaultdict
    m = np.pad(mask, 1)
    left_bg = m & ~np.roll(m, 1, axis=1)
    right_bg = m & ~np.roll(m, -1, axis=1)
    up_bg = m & ~np.roll(m, 1, axis=0)
    down_bg = m & ~np.roll(m, -1, axis=0)
    out = defaultdict(list)
    ys, xs = np.nonzero(left_bg)
    for y, x in zip(ys.tolist(), xs.tolist()):
        out[(x, y + 1)].append((x, y))            # up
    ys, xs = np.nonzero(right_bg)
    for y, x in zip(ys.tolist(), xs.tolist()):
        out[(x + 1, y)].append((x + 1, y + 1))    # down
    ys, xs = np.nonzero(up_bg)
    for y, x in zip(ys.tolist(), xs.tolist()):
        out[(x, y)].append((x + 1, y))            # right
    ys, xs = np.nonzero(down_bg)
    for y, x in zip(ys.tolist(), xs.tolist()):
        out[(x + 1, y + 1)].append((x, y + 1))    # left
    DIRS = {(1, 0): 0, (1, 1): 1, (0, 1): 2, (-1, 1): 3,
            (-1, 0): 4, (-1, -1): 5, (0, -1): 6, (1, -1): 7}
    loops = []
    for seed in list(out.keys()):
        while out.get(seed):
            v = seed
            prev = None
            loop = []
            while True:
                lst = out.get(v)
                if not lst:
                    loop = []
                    break
                if len(lst) == 1 or prev is None:
                    w = lst.pop()
                else:
                    # several outgoing edges (region touches itself at a corner):
                    # take the sharpest right turn so loops stay tight
                    din = DIRS[(v[0] - prev[0], v[1] - prev[1])]
                    best = None; bestk = None
                    for cand in lst:
                        d = DIRS[(cand[0] - v[0], cand[1] - v[1])]
                        turn = (d - din) % 8
                        if bestk is None or turn > bestk:
                            bestk = turn; best = cand
                    lst.remove(best)
                    w = best
                loop.append(v)
                prev = v
                v = w
                if v == seed:
                    break
            if len(loop) >= 4:
                loops.append(loop)
    return loops

def mask_to_loops(mask, eps=0.85, grow=1, smooth=1):
    """Trace a mask into simplified+smooth polygons (lists of xy points)."""
    m = dilate(mask, grow) if grow > 0 else mask
    out = []
    for lp in boundary_loops(m):
        pts = np.array(lp, np.float64) - 1.0
        if len(pts) > 6:
            pts = rdp(pts, eps)
        pts = smooth_pts(pts, True, smooth)
        if len(pts) >= 3:
            out.append(pts)
    return out

def mask_to_path(mask, eps=0.85, grow=1, smooth=1, guard=True):
    ds = [path_from_pts(p, True) for p in mask_to_loops(mask, eps, grow, smooth)]
    return "".join(d for d in ds if d)

# ---------------------------------------------------------------- skeleton
def thin_zhang_suen(mask):
    """Zhang-Suen thinning; returns bool skeleton."""
    img = mask.astype(np.uint8).copy()
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            P = np.pad(img, 1)
            p2 = P[:-2, 1:-1]; p3 = P[:-2, 2:]; p4 = P[1:-1, 2:]
            p5 = P[2:, 2:]; p6 = P[2:, 1:-1]; p7 = P[2:, :-2]
            p8 = P[1:-1, :-2]; p9 = P[:-2, :-2]
            B = (p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9)
            seq = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            A = np.zeros_like(B)
            for i in range(8):
                A += ((seq[i] == 0) & (seq[i+1] == 1)).astype(np.uint8)
            if step == 0:
                cond = ((p2 * p4 * p6) == 0) & ((p4 * p6 * p8) == 0)
            else:
                cond = ((p2 * p4 * p8) == 0) & ((p2 * p6 * p8) == 0)
            rem = (img == 1) & (B >= 2) & (B <= 6) & (A == 1) & cond
            if rem.any():
                img[rem] = 0
                changed = True
    return img.astype(bool)

def neighbors8(y, x):
    return ((y-1, x-1), (y-1, x), (y-1, x+1), (y, x-1),
            (y, x+1), (y+1, x-1), (y+1, x), (y+1, x+1))

def centerline_paths(skel, min_len=3):
    """Walk a 1px skeleton into polylines."""
    h, w = skel.shape
    pix = set(map(tuple, np.argwhere(skel)))
    deg = {}
    for (y, x) in pix:
        deg[(y, x)] = sum(1 for n in neighbors8(y, x) if n in pix)
    used = set()
    paths = []
    nodes = [p for p in pix if deg[p] != 2]
    nodes.sort()
    def walk(start, first):
        path = [start, first]
        used.add(first)
        prev, cur = start, first
        while True:
            if deg.get(cur, 0) != 2:
                break
            nxt = None
            for n in neighbors8(*cur):
                if n in pix and n != prev and n not in used:
                    nxt = n
                    break
            if nxt is None:
                break
            used.add(nxt)
            path.append(nxt)
            prev, cur = cur, nxt
        return path
    for s in nodes:
        for n in neighbors8(*s):
            if n in pix and n not in used:
                p = walk(s, n)
                if len(p) >= min_len:
                    paths.append(p)
    # remaining loops
    for s in sorted(pix):
        if s in used or deg.get(s, 0) != 2:
            continue
        for n in neighbors8(*s):
            if n in pix and n not in used:
                p = walk(s, n)
                if len(p) >= min_len:
                    paths.append(p + [s])
                break
    return paths
