// Native geometry per approved mechanical subject; absolute poses on every seek.
// Unsupported subjects deliberately retain an editorial plate, not a fake diagram.
function createThreeShots(specs) {
  const steel = new THREE.MeshStandardMaterial({color:0x94a3b8,metalness:.65,roughness:.32});
  const dark = new THREE.MeshStandardMaterial({color:0x263447,metalness:.45,roughness:.5});
  const accent = new THREE.MeshStandardMaterial({color:0xfbbf24,metalness:.4,roughness:.3});
  function box(parent,x,y,w,h,d,material=steel) {
    const mesh=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),material);
    mesh.position.set(x,y,0);parent.add(mesh);return mesh;
  }
  function ring(parent,x,y,r,material=steel) {
    const mesh=new THREE.Mesh(new THREE.TorusGeometry(r,.13,12,48),material);
    mesh.position.set(x,y,0);parent.add(mesh);return mesh;
  }
  const shots=specs.map((shot,index)=>{
    const group=new THREE.Group();scene.add(group);
    const moving=new THREE.Group();group.add(moving);
    const kind=shot.spec?.object || 'editorial';
    const count=shot.spec?.count || 1;
    if(kind==='chain') {
      for(let i=0;i<Math.min(count,7);i++) {
        const link=ring(moving,(i-(Math.min(count,7)-1)/2)*.7,0,.5);
        link.rotation.y=i%2*Math.PI/3;link.scale.y=1.4;
      }
    } else if(kind==='lock' || kind==='vault') {
      box(group,0,0,3,3,.5,dark);
      if(kind==='vault') {
        box(moving,1.3,0,2.6,2.6,.4);moving.position.set(-1.3,0,.5);
        ring(moving,1.3,0,.7,accent);box(moving,1.3,0,1.7,.13,.6,accent);
      } else {
        ring(group,0,1.5,1);box(moving,0,.3,.22,2.6,.7,accent);
      }
    } else if(kind==='balance') {
      box(group,0,-1,.2,2,.3);box(group,0,-2,2,.2,1);
      box(moving,0,0,4,.14,.3,accent);
      for(const side of [-1,1]) {
        box(moving,side*1.65,-.65,.06,1.3,.06);
        box(moving,side*1.65,-1.3,1.2,.12,.8);
      }
      for(let i=0;i<Math.min(count,7);i++)box(moving,-1.95+(i%3)*.3,-1.1+Math.floor(i/3)*.28,.24,.24,.4);
      box(moving,1.65,-.9,.75,.7,.6,accent);
    } else if(kind==='barrier' || kind==='wall' || kind==='bridge') {
      for(let i=0;i<5;i++)box(moving,(i-2)*.72,0,.65,kind==='bridge'?.4:2.6,.7,i===2?accent:steel);
      if(kind==='bridge')for(const x of [-1.5,1.5])box(group,x,-1,.35,2,.7,dark);
      else box(group,0,-1.5,4,.2,1,dark);
    } else if(kind==='prism') {
      moving.add(new THREE.Mesh(new THREE.CylinderGeometry(1.4,1.4,2.7,3),steel));
      box(group,-2,0,1.5,.08,.08,accent);
      for(let i=-1;i<=1;i++){const ray=box(group,2,i*.5,1.5,.06,.06,accent);ray.rotation.z=i*.25;}
    } else if(kind==='registry' || kind==='matrix' || kind==='modules') {
      const n=Math.min(count,12);
      for(let i=0;i<n;i++)box(moving,(i%3-1)*1.1,(1-Math.floor(i/3))*.85,.9,.65,.5,i===n-1?accent:steel);
    } else if(kind==='conduit' || kind==='sleeve' || kind==='aperture') {
      for(let i=0;i<5;i++){const rim=ring(group,0,0,1.4);rim.position.z=(i-2)*.4;}
      box(moving,0,0,.8,.8,.8,accent);
    } else if(kind==='anchor' || kind==='mast') {
      box(moving,0,0,.2,3,.3);ring(moving,0,1.7,.3,accent);
      box(moving,0,-1.2,2,.2,.4);box(group,0,-1.7,3,.3,1,dark);
    } else {
      box(moving,0,0,3,2,.35,kind==='seal'?accent:steel);
      if(kind==='seal')ring(moving,0,0,.7,dark);
    }
    group.rotation.set(.12,-.25,0);
    // Fit native geometry into the reserved middle band at every aspect ratio.
    const bounds=new THREE.Box3().setFromObject(group),size=bounds.getSize(new THREE.Vector3());
    const fit=Math.min((width/height)*7.2/Math.max(size.x,1),(height>width?3.8:3.3)/Math.max(size.y,1));
    group.scale.setScalar(fit);
    group.position.copy(bounds.getCenter(new THREE.Vector3()).multiplyScalar(-fit));
    group.traverse(o=>{if(o.isMesh)o.material=o.material.clone();});
    const baseline=moving.position.clone();
    group.userData={kind,action:shot.spec?.action || 'hold'};
    return {...shot,index,group,moving,baseline,tail:Math.min(.45,((specs[index+1]?.end || shot.end)-(specs[index+1]?.start || shot.end))*.12)};
  });
  window.__threeShots=shots.map(s=>s.group);
  const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x);};
  return t=>{
    for(const shot of shots) {
      const active=t>=shot.start && t<shot.end+(specs[shot.index+1]?.controls.transition==='cut'?0:shot.tail);
      shot.group.visible=active;
      if(!active)continue;
      const u=Math.min(1,(t-shot.start)/(shot.end-shot.start)),p=smooth((u-.18)/.5);
      const m=shot.moving;m.position.copy(shot.baseline);m.rotation.set(0,0,0);m.scale.setScalar(1);
      const action=shot.spec?.action;
      if(action==='balance')m.rotation.z=.18-.42*p;
      else if(action==='open-vault') {m.rotation.y=-p*1.4;}
      else if(['travel','insert','bypass'].includes(action))m.position.z+=-2+4*p;
      else if(['stamp','stamp-seal','dock','anchor'].includes(action))m.position.y+=(1-p)*1.5;
      else if(['interlock','assemble','register','expand'].includes(action))m.scale.setScalar(.65+.35*p);
      else if(action==='shear')m.rotation.z=p*.25;
      else if(action==='scan')m.position.x=-1+2*p;
      else if(action==='refract')m.rotation.y=p*.45;
      else if(action==='tension')m.scale.x=1+p*.15;
      else if(action==='block')m.position.y+=(1-p)*-2;
      else if(action==='activate' || action==='pulse')m.scale.setScalar(1+.06*Math.sin(p*Math.PI));
      // Transition affects the native object too, not only the HTML overlay.
      const cut=shot.controls.transition==='cut';
      const envelope=t>=shot.end?smooth(1-(t-shot.end)/Math.max(.001,shot.tail)):(cut || shot.index===0?1:smooth((t-shot.start)/Math.min(.45,(shot.end-shot.start)*.12)));
      shot.group.traverse(o=>{if(o.isMesh){o.material.transparent=true;o.material.opacity=envelope;}});
    }
  };
}
