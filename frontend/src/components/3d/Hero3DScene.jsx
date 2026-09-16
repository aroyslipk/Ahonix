import React, { useState, useEffect, useRef } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";

export function Hero3DScene({ scrollYProgress, className = "" }) {
  const containerRef = useRef(null);
  const [isHovered, setIsHovered] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(mq.matches);
    const handler = (e) => setPrefersReducedMotion(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  // Mouse tilt tracking
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  const springConfig = { damping: 30, stiffness: 90, mass: 0.7 };
  const smoothX = useSpring(mouseX, springConfig);
  const smoothY = useSpring(mouseY, springConfig);

  // Mouse 3D perspective transforms
  const mouseRotateX = useTransform(smoothY, [-0.5, 0.5], [7, -7]);
  const mouseRotateY = useTransform(smoothX, [-0.5, 0.5], [-10, 10]);
  const mouseTranslateZ = useTransform(smoothY, [-0.5, 0.5], [20, -15]);
  const mouseOffsetX = useTransform(smoothX, [-0.5, 0.5], [-12, 12]);

  // Scroll Reactivity transforms
  const scrollRotateY = useTransform(
    scrollYProgress || mouseX,
    [0, 1],
    [0, 15]
  );
  const scrollRotateX = useTransform(
    scrollYProgress || mouseY,
    [0, 1],
    [0, -8]
  );
  const scrollTranslateZ = useTransform(
    scrollYProgress || mouseY,
    [0, 1],
    [0, -100]
  );
  const scrollTranslateY = useTransform(
    scrollYProgress || mouseY,
    [0, 1],
    [0, 60]
  );
  const scrollScale = useTransform(
    scrollYProgress || mouseY,
    [0, 1],
    [1, 0.9]
  );

  // Combined rotation & translation
  const totalRotateX = useTransform(
    [mouseRotateX, scrollRotateX],
    ([mX, sX]) => (mX || 0) + (sX || 0)
  );
  const totalRotateY = useTransform(
    [mouseRotateY, scrollRotateY],
    ([mY, sY]) => (mY || 0) + (sY || 0)
  );
  const totalTranslateZ = useTransform(
    [mouseTranslateZ, scrollTranslateZ],
    ([mZ, sZ]) => (mZ || 0) + (sZ || 0)
  );
  const totalTranslateY = useTransform(
    [scrollTranslateY],
    ([sY]) => sY || 0
  );

  const handleMouseMove = (e) => {
    if (prefersReducedMotion || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    mouseX.set(x);
    mouseY.set(y);
  };

  const handleMouseLeave = () => {
    mouseX.set(0);
    mouseY.set(0);
    setIsHovered(false);
  };

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={handleMouseLeave}
      className={`relative select-none ${className}`}
      style={{ perspective: 1200 }}
    >
      {/* 3D Physical Sculptural A Stage */}
      <motion.div
        style={{
          rotateX: prefersReducedMotion ? 0 : totalRotateX,
          rotateY: prefersReducedMotion ? 0 : totalRotateY,
          z: prefersReducedMotion ? 0 : totalTranslateZ,
          y: prefersReducedMotion ? 0 : totalTranslateY,
          scale: prefersReducedMotion ? 1 : scrollScale,
          x: prefersReducedMotion ? 0 : mouseOffsetX,
          transformStyle: "preserve-3d",
        }}
        className="relative flex flex-col items-center justify-center transition-transform duration-75 ease-out"
      >
        {/* Soft grounded floor shadow under sculpture base */}
        <div
          className="pointer-events-none absolute -bottom-4 left-1/2 -translate-x-1/2 h-14 w-[85%] rounded-full opacity-70"
          style={{
            background:
              "radial-gradient(ellipse at 50% 50%, rgba(0, 0, 0, 0.98) 0%, rgba(0, 229, 153, 0.15) 40%, transparent 75%)",
            filter: "blur(18px)",
          }}
        />

        {/* The Isolated 3D Sculptural Emblem (ZERO card borders, ZERO rectangular box) */}
        <div className="relative w-full h-full flex items-center justify-center">
          <img
            src="/ahonix-a-isolated.png"
            alt="AHONIX 3D Sculptural Monolith"
            className="w-full h-auto object-contain pointer-events-none drop-shadow-[0_30px_70px_rgba(0,0,0,0.95)]"
            loading="eager"
            decoding="async"
            style={{
              filter: "contrast(1.05) brightness(1.02)",
            }}
          />

          {/* Interactive Specular Glint Highlight */}
          <div
            className="pointer-events-none absolute inset-0 mix-blend-overlay transition-opacity duration-300"
            style={{
              opacity: isHovered ? 0.35 : 0.12,
              background:
                "radial-gradient(circle at 45% 35%, rgba(255, 255, 255, 0.5) 0%, rgba(0, 229, 153, 0.25) 30%, transparent 60%)",
            }}
          />
        </div>
      </motion.div>
    </div>
  );
}
