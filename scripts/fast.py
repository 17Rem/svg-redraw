# -*- coding: utf-8 -*-
# Legacy resource: not used by the active svg-redraw workflow; follow SKILL.md.
"""Fast local helpers: connected components with local windows and local contour tracing."""
import numpy as np
import geo

DIRS = {(1, 0): 0, (1, 1): 1, (0, 1): 2, (-1, 1): 3,
        (-1, 0): 4, (-1, -1): 5, (0, -1): 6, (1, -1): 7}


def boundary_loops(mask):
    """Exact pixel-corner boundary walk (same semantics as geo.boundary_loops)."""
    from collections import defaultdict
    m = np.pad(mask, 1)
    left_bg = m & ~np.roll(m, 1, axis=1)
    right_bg = m & ~np.roll(m, -1, axis=1)
    up_bg = m & ~np.roll(m, 1, axis=0)
    down_bg = m & ~np.roll(m, -1, axis=0)
    out = defaultdict(list)
    ys, xs = np.nonzero(left_bg)
    for y, x in zip(ys.tolist(), xs.tolist()):
        out[(x, y + 1)].append((x, y))
    ys, xs = np.nonzero(right_bg)
    for y, x in zip(ys.tolist(), xs.tolist()):
        out[(x + 1, y)].append((x + 1, y + 1))
    ys, xs = np.nonzero(up_bg)
    for y, x in zip(ys.tolist(), xs.tolist()):
        out[(x, y)].append((x + 1, y))
    ys, xs = np.nonzero(down_bg)
    for y, x in zip(ys.tolist(), xs.tolist()):
        out[(x + 1, y + 1)].append((x, y + 1))
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


def trace_local(maskc, eps=0.65, grow=1, smooth=1, rdp=True):
    """Trace a full-size bool mask inside its own bounding box; returns list of point arrays."""
    ys, xs = np.nonzero(maskc)
    if len(ys) == 0:
        return []
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    pad = grow + 2
    Y0 = max(0, y0 - pad); Y1 = min(maskc.shape[0], y1 + pad + 1)
    X0 = max(0, x0 - pad); X1 = min(maskc.shape[1], x1 + pad + 1)
    sub = maskc[Y0:Y1, X0:X1]
    if grow > 0:
        sub = geo.dilate(sub, grow)
    off = np.array([X0, Y0], np.float64)   # loop points are (x, y)
    res = []
    for lp in boundary_loops(sub):
        pts = np.array(lp, np.float64) - 1.0 + off
        if rdp and len(pts) > 6:
            pts = geo.rdp(pts, eps)
        pts = geo.smooth_pts(pts, True, smooth)
        if len(pts) >= 3:
            res.append(pts)
    return res


def path_local(maskc, eps=0.65, grow=1, smooth=1, linear=False, r=1):
    fn = geo.path_from_pts_linear if linear else geo.path_from_pts
    ds = [fn(p, True, r) for p in trace_local(maskc, eps, grow, smooth)]
    return "".join(d for d in ds if d)


def components_fast(mask, minpx=1):
    """Connected components; returns list of (y, x) index arrays."""
    return geo.components(mask, minpx=minpx)


def merge_specks(labels, K, limit_fn, rounds=3, report=None):
    """Reassign tiny same-label specks to their dominant neighbour, locally."""
    H, W = labels.shape
    for rnd in range(rounds):
        moved = 0
        for lb in range(K):
            m = labels == lb
            n = int(m.sum())
            if n == 0:
                continue
            for c in geo.components(m, minpx=1):
                if len(c) >= limit_fn(c, H, W):
                    continue
                cy0, cx0 = c.min(0); cy1, cx1 = c.max(0)
                pad = 3
                Y0 = max(0, cy0 - pad); Y1 = min(H, cy1 + pad + 1)
                X0 = max(0, cx0 - pad); X1 = min(W, cx1 + pad + 1)
                win = labels[Y0:Y1, X0:X1]
                loc = np.zeros(win.shape, bool)
                loc[c[:, 0] - Y0, c[:, 1] - X0] = True
                ring = geo.dilate(loc, 2) & ~loc
                nb = win[ring]
                nb = nb[nb >= 0]
                nb = nb[nb != lb]
                if nb.size == 0:
                    nb = win[geo.dilate(loc, 3) & ~loc]
                    nb = nb[nb != lb]
                    if nb.size == 0:
                        continue
                vals, counts = np.unique(nb, return_counts=True)
                labels[c[:, 0], c[:, 1]] = int(vals[counts.argmax()])
                moved += 1
        if report:
            report(rnd, moved)
        if moved == 0:
            break
    return labels
