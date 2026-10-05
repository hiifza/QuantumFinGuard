import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { MeshDistortMaterial, Icosahedron } from '@react-three/drei'
import type { Mesh } from 'three'

interface RiskOrbProps {
  /** 0-100. Drives both the color (emerald -> amber -> coral) and the
   * distortion/pulse intensity — a higher aggregate risk reads as a
   * more agitated, warmer object. This is the real signal, not a
   * decorative animation running regardless of data. */
  riskLevel: number
}

function colorForRisk(riskLevel: number): string {
  if (riskLevel < 30) return '#4E8F76' // emerald
  if (riskLevel < 65) return '#C99A56' // amber
  return '#C97B63' // coral
}

function OrbMesh({ riskLevel }: RiskOrbProps) {
  const meshRef = useRef<Mesh>(null)
  const color = useMemo(() => colorForRisk(riskLevel), [riskLevel])
  const distortIntensity = 0.25 + (riskLevel / 100) * 0.45

  useFrame((_, delta) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += delta * 0.15
      meshRef.current.rotation.x += delta * 0.04
    }
  })

  return (
    <Icosahedron ref={meshRef} args={[1.4, 4]}>
      <MeshDistortMaterial
        color={color}
        distort={distortIntensity}
        speed={1.4 + riskLevel / 60}
        roughness={0.35}
        metalness={0.2}
        opacity={0.92}
        transparent
      />
    </Icosahedron>
  )
}

export function RiskOrb({ riskLevel }: RiskOrbProps) {
  return (
    <Canvas camera={{ position: [0, 0, 4.2], fov: 42 }} dpr={[1, 1.5]} gl={{ alpha: true, antialias: true }}>
      <ambientLight intensity={0.5} />
      <pointLight position={[3, 3, 3]} intensity={60} color="#ffffff" />
      <pointLight position={[-3, -2, -2]} intensity={20} color={colorForRisk(riskLevel)} />
      <OrbMesh riskLevel={riskLevel} />
    </Canvas>
  )
}
