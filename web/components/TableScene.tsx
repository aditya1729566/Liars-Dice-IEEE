'use client';
import { Canvas, useFrame } from '@react-three/fiber';
import { RoundedBox } from '@react-three/drei';
import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import type { Group } from 'three';

const pipPositions: Record<number, [number, number][]> = {
  1: [[0,0]], 2: [[-.24,-.24],[.24,.24]], 3: [[-.24,-.24],[0,0],[.24,.24]],
  4: [[-.24,-.24],[.24,.24],[-.24,.24],[.24,-.24]],
  5: [[-.24,-.24],[.24,.24],[-.24,.24],[.24,-.24],[0,0]],
  6: [[-.24,-.25],[0,-.25],[.24,-.25],[-.24,.25],[0,.25],[.24,.25]]
};
function Die({value,position,concealed=false}:{value:number;position:[number,number,number];concealed?:boolean}){
  const pips=useMemo(()=>pipPositions[value] ?? pipPositions[1],[value]);
  const ref=useRef<Group>(null),start=useRef(0);
  useEffect(()=>{start.current=performance.now();},[value,concealed]);
  useFrame(()=>{if(!ref.current)return;const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;const t=reduced?1:Math.min(1,(performance.now()-start.current)/650);const settle=(1-t)*(1-t);ref.current.position.y=position[1]+.65*settle;ref.current.rotation.x=2.4*settle;ref.current.rotation.z=1.5*settle;});
  return <group ref={ref} position={position} rotation={[0,0.14,0]}>
    <RoundedBox args={[.76,.76,.76]} radius={.075} smoothness={4} castShadow receiveShadow>
      <meshStandardMaterial color={concealed?'#445056':'#e8e2d2'} roughness={.35} metalness={concealed?.48:.08}/>
    </RoundedBox>
    {!concealed && pips.map(([x,z],i)=><mesh key={i} position={[x,.386,z]} rotation={[-Math.PI/2,0,0]}>
      <circleGeometry args={[.065,18]}/><meshStandardMaterial color="#171b1b" roughness={.8}/>
    </mesh>)}
    {concealed && <mesh position={[0,.389,0]} rotation={[-Math.PI/2,0,0]}><ringGeometry args={[.13,.16,32]}/><meshBasicMaterial color="#83a2a8"/></mesh>}
  </group>;
}
function Stage({hand,aiCount,reveal}:{hand:number[];aiCount:number;reveal?:number[]}){
  return <>
    <color attach="background" args={['#101719']}/>
    <ambientLight intensity={.38}/>
    <spotLight position={[-4,7,5]} intensity={70} angle={.55} penumbra={.8} color="#e9a45d" castShadow shadow-mapSize={[1024,1024]}/>
    <spotLight position={[5,5,-5]} intensity={43} angle={.6} penumbra={.8} color="#7aabb9"/>
    <mesh receiveShadow position={[0,-.4,0]} rotation={[-Math.PI/2,0,0]}><planeGeometry args={[20,13]}/><meshBasicMaterial color="#284139"/></mesh>
    <mesh position={[0,-.44,0]} rotation={[-Math.PI/2,0,0]}><torusGeometry args={[3.95,.035,10,96]}/><meshStandardMaterial color="#9d815f" metalness={.75} roughness={.32}/></mesh>
    <mesh position={[0,-.42,0]} rotation={[-Math.PI/2,0,0]}><ringGeometry args={[2.95,2.98,96]}/><meshStandardMaterial color="#5f665e" transparent opacity={.4}/></mesh>
    {(reveal ?? Array.from({length:aiCount},()=>1)).map((v,i)=><Die key={'ai'+i} value={v} concealed={!reveal} position={[(i-(aiCount-1)/2)*1.03,.06,-1.55]}/>)}
    {hand.map((v,i)=><Die key={'h'+i} value={v} position={[(i-(hand.length-1)/2)*1.03,.08,1.55]}/>)}
  </>;
}
export default function TableScene({hand,aiCount,reveal}:{hand:number[];aiCount:number;reveal?:number[]}){
  const [failed,setFailed]=useState(false);
  const [supported]=useState(()=>typeof window==='undefined'||!!document.createElement('canvas').getContext('webgl2'));
  if(failed||!supported) return <div className="table-fallback" role="img" aria-label={`Your dice: ${hand.join(', ')}. AI dice: ${reveal?reveal.join(', '):'concealed'}.`}><div className="fallback-row">AI {reveal?reveal.map((n,i)=><b key={i}>{n}</b>):Array.from({length:aiCount},(_,i)=><b key={i}>?</b>)}</div><div className="felt-line"/><div className="fallback-row">YOU {hand.map((n,i)=><b key={i}>{n}</b>)}</div></div>;
  return <div className="table-canvas" role="img" aria-label={`Your dice: ${hand.join(', ')}. AI has ${aiCount} ${reveal?'revealed':'concealed'} dice.`}>
    <Canvas shadows dpr={[1,1.5]} camera={{position:[0,5.7,7.7],fov:42}} onCreated={({gl})=>{gl.domElement.addEventListener('webglcontextlost',()=>setFailed(true),{once:true});}}>
      <Suspense fallback={null}><Stage hand={hand} aiCount={aiCount} reveal={reveal}/></Suspense>
    </Canvas>
  </div>;
}
