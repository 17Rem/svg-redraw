// Legacy resource: not used by the active svg-redraw workflow; follow SKILL.md.
/**
 * Generic "redraw playback" video for a traced SVG.
 *
 * Layout: reference image on the left, the SVG redraw in the middle, the ten stage rows on
 * the right, timeline at the bottom, and an 8 s same-position wipe comparison at the end.
 *
 * Wire it up in your Remotion root:
 *
 *   import {makeRedrawVideo} from './RedrawVideo';
 *   import {MY_ART_SVG, MY_ART_DURATION, MY_ART_W, MY_ART_H,
 *           MY_ART_STAGES} from './my_art';
 *
 *   const MyArtDrawing = makeRedrawVideo({
 *     SVG: MY_ART_SVG,
 *     DURATION: MY_ART_DURATION,
 *     W: MY_ART_W,
 *     H: MY_ART_H,
 *     STAGES: MY_ART_STAGES,
 *   }, {
 *     title: 'MY ART',
 *     subtitle: '纯 SVG 重绘 · 完整绘制流程',
 *     refImage: staticFile('reference.jpg'),   // omit to hide the reference panel
 *     pathCount: '12,330',
 *   });
 *
 *   <Composition id="MyArtDrawing" component={MyArtDrawing}
 *     durationInFrames={Math.round((MY_ART_DURATION + 8) * 30)}
 *     fps={30} width={1920} height={1080} />
 *
 * The two effects below are not optional: Remotion may rebuild the injected SVG subtree
 * between frames inside a reused browser tab, and styling detached nodes silently leaves
 * every frame showing the finished artwork. paint() re-binds whenever that happens.
 */
import React, {useEffect, useLayoutEffect, useMemo, useRef} from 'react';
import {AbsoluteFill, Img, useCurrentFrame, useVideoConfig} from 'remotion';

export type ArtModule = {
  SVG: string;
  DURATION: number;
  W: number;
  H: number;
  STAGES: {key: string; label: string; from: number; to: number}[];
};

export type RedrawOptions = {
  title: string;
  subtitle?: string;
  refImage?: string;
  pathCount?: string;
  layerCount?: number;
  stageDesc?: Record<string, string>;
  footer?: string;
};

const FONT = '"PingFang SC","Microsoft YaHei",ui-sans-serif,system-ui,sans-serif';
const OUTRO = 8;

const DEFAULT_DESC: Record<string, string> = {
  sketch: '头身比例 · 位置 · 廓形',
  bg: '背景装饰 · 氛围',
  base: '按分区铺入固有色',
  shadow: '一级阴影 · 建立体积',
  deep: '二级暗部 · 压深重色',
  light: '高光 · 提亮亮面',
  line: '极细结构线 · 收形',
  ink: '墨线勾线 · 定稿轮廓',
  face: '五官 · 细节刻画',
  fx: '最终光效',
};

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);
const smooth = (x: number) => {
  const t = clamp01(x);
  return t * t * (3 - 2 * t);
};
const easeOut = (x: number) => 1 - Math.pow(1 - clamp01(x), 3);
const seg = (p: number, a: number, b: number) => clamp01((p - a) / (b - a));

type Node = {el: SVGElement; t: number; d: number; o: number};

export const makeRedrawVideo = (art: ArtModule, opts: RedrawOptions): React.FC => {
  const ASPECT = art.W / art.H;
  const DRAW_END = art.DURATION;
  const TOTAL = DRAW_END + OUTRO;
  const STAGES = art.STAGES;
  const DESC = {...DEFAULT_DESC, ...(opts.stageDesc ?? {})};

  const Panel: React.FC<{
    x: number;
    y: number;
    w: number;
    h: number;
    label: string;
    accent: string;
    children: React.ReactNode;
  }> = ({x, y, w, h, label, accent, children}) => (
    <div style={{position: 'absolute', left: x, top: y, width: w}}>
      <div style={{fontSize: 14, letterSpacing: 4, color: accent, marginBottom: 10,
                   display: 'flex', alignItems: 'center', gap: 10}}>
        <span style={{display: 'inline-block', width: 16, height: 2, background: accent}}/>
        {label}
      </div>
      <div style={{position: 'relative', width: w, height: h - 34, borderRadius: 10,
                   overflow: 'hidden', background: '#fbf9fd',
                   boxShadow: '0 26px 70px rgba(0,0,0,.6), 0 0 0 1px rgba(255,255,255,.08) inset'}}>
        {children}
      </div>
    </div>
  );

  return function RedrawVideo() {
    const frame = useCurrentFrame();
    const {fps, width, height} = useVideoConfig();
    const time = frame / fps;

    const holderRef = useRef<HTMLDivElement>(null);
    const cacheRef = useRef<Node[] | null>(null);

    const padX = 72;
    const headerH = 104;
    const footerH = 78;
    const panelH = height - headerH - footerH - 24;
    const panelW = Math.round(panelH * ASPECT);
    const gap = 34;
    const leftX = padX;
    const rightX = leftX + panelW + gap;
    const sideX = rightX + panelW + 54;
    const sideW = width - sideX - padX;
    const panelY = headerH;

    const drawT = Math.min(time, DRAW_END);
    const hasRef = Boolean(opts.refImage);

    const collect = (root: SVGSVGElement): Node[] => {
      const els = Array.from(root.querySelectorAll('[data-t]')) as SVGElement[];
      return els.map((el) => ({
        el,
        t: parseFloat(el.getAttribute('data-t') || '0'),
        d: parseFloat(el.getAttribute('data-d') || '0.3'),
        o: -1,
      }));
    };

    const paint = () => {
      const root = holderRef.current?.querySelector('#redraw-art') as SVGSVGElement | null;
      if (!root) {
        return;
      }
      let nodes = cacheRef.current;
      if (!nodes || nodes.length === 0 || !nodes[0].el.isConnected ||
          nodes[0].el.ownerSVGElement !== root) {
        nodes = collect(root);
        cacheRef.current = nodes;
      }
      for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        const v = smooth((drawT - n.t) / n.d);
        if (v !== n.o) {
          n.o = v;
          n.el.style.opacity = String(v);
        }
      }
    };

    useLayoutEffect(() => {
      paint();
    });
    useEffect(() => {
      paint();
    });

    const active = useMemo(
      () => STAGES.reduce((acc, s, i) => (drawT >= s.from ? i : acc), -1),
      [drawT]
    );
    const finished = drawT >= DRAW_END - 0.05;
    const progress = clamp01(drawT / DRAW_END);

    const wipeT = useMemo(() => {
      if (time < DRAW_END + 0.6) {
        return 0;
      }
      const a = seg(time, DRAW_END + 0.9, DRAW_END + 3.6);
      const b = seg(time, DRAW_END + 5.2, DRAW_END + 7.6);
      return a > 0 && b === 0 ? smooth(a) : b > 0 ? 1 - smooth(b) : a >= 1 ? 1 : 0;
    }, [time]);
    const wipeOn = time >= DRAW_END + 0.3;

    const stageFade = easeOut(seg(time, 0.15, 1.1));
    const totalFrames = Math.round(TOTAL * fps);
    const status = finished
      ? '绘制完成 · 与参考原图并排比对'
      : active >= 0
      ? STAGES[active].label
      : '准备画纸';

    return (
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(120% 90% at 50% -18%, #2d2649 0%, #1c1830 46%, #12101f 100%)',
          fontFamily: FONT,
          color: '#f1ecfa',
        }}
      >
        <div style={{position: 'absolute', top: 0, left: padX, right: padX, height: headerH,
                     display: 'flex', alignItems: 'center', gap: 26, opacity: stageFade}}>
          <span style={{fontSize: 30, letterSpacing: 12, fontWeight: 600}}>{opts.title}</span>
          <span style={{fontSize: 16, letterSpacing: 5, color: '#8f88ab'}}>{opts.subtitle ?? ''}</span>
          <span style={{marginLeft: 'auto', fontSize: 16, letterSpacing: 3,
                        color: finished ? '#b3a4e6' : '#8f88ab'}}>
            {status}
          </span>
        </div>

        {hasRef ? (
          <Panel x={leftX} y={panelY} w={panelW} h={panelH} label="参考原图" accent="#6f6790">
            <Img src={opts.refImage as string}
                 style={{width: '100%', height: '100%', objectFit: 'contain', display: 'block'}}/>
          </Panel>
        ) : null}

        <Panel x={hasRef ? rightX : leftX} y={panelY}
               w={hasRef ? panelW : Math.round(panelH * ASPECT * 1.25)} h={panelH}
               label="SVG 重绘" accent="#b3a4e6">
          <div ref={holderRef} style={{width: '100%', height: '100%'}}
               dangerouslySetInnerHTML={{__html: art.SVG}}/>
          {hasRef && wipeOn ? (
            <>
              <div style={{position: 'absolute', inset: 0,
                           clipPath: `inset(0 ${100 - wipeT * 100}% 0 0)`}}>
                <Img src={opts.refImage as string}
                     style={{width: '100%', height: '100%', objectFit: 'contain', display: 'block'}}/>
              </div>
              {wipeT > 0.002 && wipeT < 0.998 ? (
                <div style={{position: 'absolute', top: 0, bottom: 0, left: `${wipeT * 100}%`,
                             width: 3, marginLeft: -1.5, background: '#ffffff',
                             boxShadow: '0 0 16px rgba(255,255,255,.95)'}}/>
              ) : null}
              <div style={{position: 'absolute', left: 14, bottom: 12, fontSize: 14, letterSpacing: 3,
                           color: '#fff', background: 'rgba(20,17,36,.72)', padding: '5px 12px',
                           borderRadius: 999, opacity: wipeT > 0.06 ? 1 : 0}}>
                参考原图
              </div>
              <div style={{position: 'absolute', right: 14, bottom: 12, fontSize: 14, letterSpacing: 3,
                           color: '#fff', background: 'rgba(20,17,36,.72)', padding: '5px 12px',
                           borderRadius: 999, opacity: wipeT < 0.94 ? 1 : 0}}>
                SVG 重绘
              </div>
            </>
          ) : null}
        </Panel>

        <div style={{position: 'absolute', left: sideX, top: panelY, width: sideW, opacity: stageFade}}>
          <div style={{fontSize: 15, letterSpacing: 5, color: '#7d76a0', marginBottom: 18}}>
            绘 制 阶 段
          </div>
          {STAGES.map((s, i) => {
            const p = clamp01((drawT - s.from) / (s.to - s.from));
            const on = i <= active;
            const now = i === active && !finished;
            const rowH = (panelH - 130) / STAGES.length;
            return (
              <div key={s.key} style={{height: rowH, opacity: on ? 1 : 0.34,
                                       display: 'flex', flexDirection: 'column', justifyContent: 'center',
                                       borderLeft: `3px solid ${now ? '#b3a4e6' : 'transparent'}`,
                                       paddingLeft: now ? 14 : 17}}>
                <div style={{display: 'flex', alignItems: 'baseline', gap: 12}}>
                  <span style={{fontSize: 14, color: now ? '#b3a4e6' : '#6b6489'}}>
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span style={{fontSize: 20, letterSpacing: 2,
                                color: on ? '#ffffff' : '#a69fbe',
                                fontWeight: now ? 700 : on ? 600 : 400}}>
                    {s.label}
                  </span>
                  <span style={{marginLeft: 'auto', fontSize: 14, color: '#6b6489'}}>
                    {Math.round(p * 100)}%
                  </span>
                </div>
                <div style={{fontSize: 13, color: '#6b6489', letterSpacing: 1,
                             marginTop: 4, marginBottom: 7}}>
                  {DESC[s.key] ?? ''}
                </div>
                <div style={{height: 5, borderRadius: 99, background: 'rgba(255,255,255,.09)',
                             overflow: 'hidden'}}>
                  <div style={{width: `${p * 100}%`, height: '100%', borderRadius: 99,
                               background: 'linear-gradient(90deg,#8f7fd8,#b3a4e6)'}}/>
                </div>
              </div>
            );
          })}
        </div>

        <div style={{position: 'absolute', left: padX, right: padX, bottom: 26, height: footerH - 26,
                     display: 'flex', alignItems: 'center', gap: 22, opacity: stageFade}}>
          <span style={{fontSize: 15, color: '#8f88ab', letterSpacing: 2}}>0s</span>
          <div style={{flex: 1, height: 6, borderRadius: 99, background: 'rgba(255,255,255,.12)',
                       overflow: 'hidden'}}>
            <div style={{width: `${progress * 100}%`, height: '100%', borderRadius: 99,
                         background: 'linear-gradient(90deg,#8f7fd8,#ffffff)'}}/>
          </div>
          <span style={{fontSize: 17, color: '#cfc7e4', letterSpacing: 2,
                        fontVariantNumeric: 'tabular-nums'}}>
            {time.toFixed(1)}s / {TOTAL.toFixed(0)}s
          </span>
          <span style={{fontSize: 15, color: '#5f5880', letterSpacing: 3}}>
            {opts.footer ??
              `原生 SVG 路径分层绘制 · ${opts.pathCount ?? ''} 条 path · ${opts.layerCount ?? 10} 个图层 · 0 张位图`}
            {' '}（第 {(frame + 1).toLocaleString()} / {totalFrames.toLocaleString()} 帧）
          </span>
        </div>
      </AbsoluteFill>
    );
  };
};
