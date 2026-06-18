import { useEffect, useRef } from "react";

const NODES = [
  { id: 0, x: 15, y: 40, r: 3 },
  { id: 1, x: 28, y: 25, r: 2.5 },
  { id: 2, x: 40, y: 55, r: 3.5 },
  { id: 3, x: 52, y: 30, r: 2.5 },
  { id: 4, x: 55, y: 65, r: 3 },
  { id: 5, x: 68, y: 20, r: 2 },
  { id: 6, x: 72, y: 50, r: 3 },
  { id: 7, x: 82, y: 35, r: 2.5 },
  { id: 8, x: 88, y: 60, r: 2 },
  { id: 9, x: 25, y: 70, r: 2 },
  { id: 10, x: 60, y: 75, r: 2.5 },
  { id: 11, x: 45, y: 15, r: 2 },
  { id: 12, x: 78, y: 68, r: 2 },
];

const EDGES = [
  [0, 1], [0, 2], [0, 9],
  [1, 3], [1, 11],
  [2, 4], [2, 9],
  [3, 5], [3, 6],
  [4, 6], [4, 10],
  [5, 7],
  [6, 7], [6, 10],
  [7, 8], [7, 12],
  [8, 12],
  [9, 10],
  [11, 3],
];

const PULSE_ROUTES = [
  { from: 2, to: 4 },
  { from: 4, to: 6 },
  { from: 6, to: 10 },
  { from: 0, to: 2 },
  { from: 0, to: 1 },
  { from: 1, to: 3 },
  { from: 3, to: 6 },
  { from: 7, to: 8 },
  { from: 5, to: 7 },
  { from: 9, to: 10 },
];

function getCoords(id) {
  const n = NODES[id];
  return { x: n.x, y: n.y };
}

export function HeroNetworkBackground() {
  const canvasRef = useRef(null);
  const animRef = useRef(null);
  const particlesRef = useRef([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let frameId;

    function resize() {
      const parent = canvas.parentElement;
      canvas.width = parent.offsetWidth;
      canvas.height = parent.offsetHeight;
    }
    resize();
    window.addEventListener("resize", resize);

    const w = () => canvas.width;
    const h = () => canvas.height;

    function toPixel(px, py) {
      return { x: (px / 100) * w(), y: (py / 100) * h() };
    }

    class Pulse {
      constructor(edgeIdx) {
        this.edgeIdx = edgeIdx;
        this.progress = Math.random();
        this.speed = 0.15 + Math.random() * 0.12;
        this.size = 1.5 + Math.random() * 1;
        this.trail = [];
      }

      update(dt) {
        this.progress += this.speed * dt;
        this.trail.push(this.progress);
        if (this.trail.length > 20) this.trail.shift();
        if (this.progress > 1) {
          this.progress = 0;
          this.trail = [];
        }
      }

      getPosition() {
        const route = PULSE_ROUTES[this.edgeIdx];
        const a = getCoords(route.from);
        const b = getCoords(route.to);
        return {
          x: a.x + (b.x - a.x) * this.progress,
          y: a.y + (b.y - a.y) * this.progress,
        };
      }

      draw(ctx) {
        const route = PULSE_ROUTES[this.edgeIdx];
        const a = getCoords(route.from);
        const b = getCoords(route.to);

        for (let i = 0; i < this.trail.length; i++) {
          const t = this.trail[i];
          const px = a.x + (b.x - a.x) * t;
          const py = a.y + (b.y - a.y) * t;
          const p = toPixel(px, py);
          const alpha = (i / this.trail.length) * 0.5;
          ctx.beginPath();
          ctx.arc(p.x, p.y, this.size * (i / this.trail.length), 0, Math.PI * 2);
          ctx.fillStyle = `rgba(185, 255, 102, ${alpha})`;
          ctx.fill();
        }

        const pos = this.getPosition();
        const p = toPixel(pos.x, pos.y);
        ctx.beginPath();
        ctx.arc(p.x, p.y, this.size * 1.5, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(185, 255, 102, 0.7)";
        ctx.fill();
      }
    }

    particlesRef.current = PULSE_ROUTES.map((_, i) => new Pulse(i));

    let lastTime = 0;

    function draw(time) {
      const dt = Math.min((time - lastTime) / 1000, 0.05);
      lastTime = time;

      ctx.clearRect(0, 0, w(), h());

      for (const edge of EDGES) {
        const a = getCoords(edge[0]);
        const b = getCoords(edge[1]);
        const p1 = toPixel(a.x, a.y);
        const p2 = toPixel(b.x, b.y);

        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      for (const node of NODES) {
        const p = toPixel(node.x, node.y);
        ctx.beginPath();
        ctx.arc(p.x, p.y, node.r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255, 255, 255, 0.04)";
        ctx.fill();

        const pulse = Math.sin(Date.now() * 0.001 - node.id) * 0.5 + 0.5;
        ctx.beginPath();
        ctx.arc(p.x, p.y, node.r + 4 + pulse * 6, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(185, 255, 102, ${0.04 + pulse * 0.06})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      for (const particle of particlesRef.current) {
        particle.update(dt);
        particle.draw(ctx);
      }

      frameId = requestAnimationFrame(draw);
    }

    frameId = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        opacity: 0.6,
        maskImage: "radial-gradient(ellipse 80% 60% at 50% 40%, black 30%, transparent 70%)",
        WebkitMaskImage: "radial-gradient(ellipse 80% 60% at 50% 40%, black 30%, transparent 70%)",
      }}
    />
  );
}
