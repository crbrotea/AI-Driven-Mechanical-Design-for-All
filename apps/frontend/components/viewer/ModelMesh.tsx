'use client'
import { useEffect, useRef } from 'react'
import { useGLTF } from '@react-three/drei'
import { useUIStore } from '@/lib/stores/uiStore'
import type { Group, Mesh, MeshStandardMaterial } from 'three'

export function ModelMesh({ glbUrl }: { glbUrl: string }) {
  const { scene } = useGLTF(glbUrl)
  const wireframe = useUIStore((s) => s.viewerWireframe)
  const groupRef = useRef<Group>(null)

  useEffect(() => {
    scene.traverse((obj) => {
      if ((obj as Mesh).isMesh) {
        const mesh = obj as Mesh
        const mat = mesh.material as MeshStandardMaterial
        if (mat && 'wireframe' in mat) mat.wireframe = wireframe
        mesh.castShadow = true
        mesh.receiveShadow = true
      }
    })
  }, [wireframe, scene])

  return <primitive ref={groupRef} object={scene} />
}
