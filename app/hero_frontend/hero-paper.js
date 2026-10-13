/* Closed subdivided paper geometry. Local math only; no clock or business state. */
(function(global){
  'use strict';
  function createGeometry(columns=16,rows=20){
    const vertices=[],indices=[];
    function face(width,height,point,normal,front){
      const offset=vertices.length/9;
      const origin=point(0,0),a=point(1,0).map((value,index)=>value-origin[index]),b=point(0,1).map((value,index)=>value-origin[index]);
      const outward=(a[1]*b[2]-a[2]*b[1])*normal[0]+(a[2]*b[0]-a[0]*b[2])*normal[1]+(a[0]*b[1]-a[1]*b[0])*normal[2]>0;
      for(let y=0;y<=height;y++)for(let x=0;x<=width;x++){
        const p=point(x/width,y/height);
        vertices.push(...p,...normal,p[0]+.5,p[1]+.5,front);
      }
      for(let y=0;y<height;y++)for(let x=0;x<width;x++){
        const a=offset+y*(width+1)+x,b=a+1,c=a+width+2,d=a+width+1;
        if(outward)indices.push(a,b,c,a,c,d);else indices.push(a,c,b,a,d,c);
      }
    }
    face(columns,rows,(u,v)=>[u-.5,v-.5,.5],[0,0,1],1);
    face(columns,rows,(u,v)=>[u-.5,v-.5,-.5],[0,0,-1],0);
    face(1,rows,(u,v)=>[.5,v-.5,u-.5],[1,0,0],0);
    face(1,rows,(u,v)=>[-.5,v-.5,u-.5],[-1,0,0],0);
    face(columns,1,(u,v)=>[u-.5,.5,v-.5],[0,1,0],0);
    face(columns,1,(u,v)=>[u-.5,-.5,v-.5],[0,-1,0],0);
    const source=new Float32Array(vertices);
    const gridU=new Uint16Array(source.length/9),gridV=new Uint16Array(source.length/9);
    for(let i=0;i<gridU.length;i++){gridU[i]=Math.round((source[i*9]+.5)*columns);gridV[i]=Math.round((source[i*9+1]+.5)*rows);}
    return {source,data:source.slice(),indices:new Uint16Array(indices),columns,rows,gridU,gridV,uCache:new Float64Array((columns+1)*6),vCache:new Float64Array((rows+1)*3)};
  }
  function deform(geometry,size,bend,curl){
    const source=geometry.source,data=geometry.data,sx=size[0],sy=size[1],sz=size[2];
    const uCache=geometry.uCache,vCache=geometry.vCache,invX=1/sx,invY=1/sy,invZ=1/sz;
    // Trigonometry is shared by an entire grid column; buffers and lookup
    // tables are allocated once and reused for every paper and every frame.
    for(let col=0;col<=geometry.columns;col++){
      const i=col*6,u=col/geometry.columns,u2=u*u,theta=bend*u;
      uCache[i]=sx*Math.cos(theta);uCache[i+1]=sx*Math.sin(theta);uCache[i+2]=u2*u;uCache[i+3]=u2*u2;
      uCache[i+4]=Math.abs(bend)<1e-6?sx*(u-.5):sx*(Math.sin(theta)/bend-.5);
      uCache[i+5]=Math.abs(bend)<1e-6?0:sx*(1-Math.cos(theta))/bend;
    }
    for(let row=0;row<=geometry.rows;row++){
      const i=row*3,v=row/geometry.rows,v3=v*v*v,w=1-v,w3=w*w*w;
      vCache[i]=v3*v+.22*w3*w;vCache[i+1]=4*v3-.88*w3;vCache[i+2]=sy*(v-.5);
    }
    for(let i=0;i<source.length;i+=9){
      const col=geometry.gridU[i/9]*6,row=geometry.gridV[i/9]*3,weight=vCache[row];
      const dx=uCache[col],dz=uCache[col+1]+4*curl*sx*uCache[col+2]*weight,dv=curl*sx*uCache[col+3]*vCache[row+1];
      // Analytic surface normal is the cross product of both curved tangents.
      let nx=-dz*sy,ny=-dx*dv,nz=dx*sy;
      const normalLength=Math.sqrt(nx*nx+ny*ny+nz*nz)||1;nx/=normalLength;ny/=normalLength;nz/=normalLength;
      const edge=source[i+2]*sz;
      data[i]=(uCache[col+4]+nx*edge)*invX;
      data[i+1]=(vCache[row+2]+ny*edge)*invY;
      data[i+2]=(uCache[col+5]+curl*sx*uCache[col+3]*weight+nz*edge)*invZ;
      let faceX=nx,faceY=ny,faceZ=nz;
      if(source[i+3]){
        const side=source[i+3];faceX=(sy*nz-dv*ny)*side;faceY=dv*nx*side;faceZ=-sy*nx*side;
      }else if(source[i+4]){
        const side=source[i+4];faceX=ny*dz*side;faceY=(nz*dx-nx*dz)*side;faceZ=-ny*dx*side;
      }else if(source[i+5]<0){faceX=-nx;faceY=-ny;faceZ=-nz;}
      // Store the local covector. uNormal removes model scaling in the shader.
      // This retains the original model matrices, dimensions and texture UVs.
      const length=source[i+3]||source[i+4]?Math.sqrt(faceX*faceX+faceY*faceY+faceZ*faceZ)||1:1;
      data[i+3]=faceX/length*sx;data[i+4]=faceY/length*sy;data[i+5]=faceZ/length*sz;
    }
    return data;
  }
  global.QMHeroPaper={version:'2026-10-09.13',createGeometry,deform};
})(typeof window!=='undefined'?window:globalThis);
