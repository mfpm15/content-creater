/** Pure validation shared by the renderer entry and composition. No URLs/assets/scripts. */
/** @param {string} text @returns {string[]} */
export function literalNumbers(text) {
  return text.match(/(?<![\w.,+−-])[+−-]?\d+(?:[.,]\d+)*(?:\s*%)?/g) || [];
}

export function validateManifest(value) {
  const fail = () => { throw new Error('Invalid Video Studio timeline'); };
  const integer = n => Number.isSafeInteger(n);
  const text = (s, max) => typeof s === 'string' && s.length <= max;
  const plain = o => o && typeof o === 'object' && Object.getPrototypeOf(o) === Object.prototype;
  if (!plain(value)) fail();
  const keys = ['version','width','height','fps','totalFrames','topic','brand','shots','captions'];
  if (Object.keys(value).some(key => !keys.includes(key))) fail();
  if (value.version !== 1 || ![30,60].includes(value.fps) || !integer(value.totalFrames) || value.totalFrames < 1 || value.totalFrames > 600*value.fps) fail();
  if (![value.width,value.height].every(n => integer(n) && n >= 128 && n <= 3840 && n % 2 === 0) || !text(value.topic,500)) fail();
  const brand = value.brand;
  if (!plain(brand) || Object.keys(brand).some(k => !['background','accent','text','wordmark','font'].includes(k)) ||
      !['background','accent','text'].every(k => /^#[0-9a-fA-F]{6}$/.test(brand[k])) || !text(brand.wordmark,100) || !['Arial','Verdana','Georgia','Tahoma'].includes(brand.font)) fail();
  if (!Array.isArray(value.shots) || value.shots.length < 1 || value.shots.length > 200 || !Array.isArray(value.captions) || value.captions.length > 10000) fail();
  let end = 0;
  const ids = new Set();
  for (const shot of value.shots) {
    if (!plain(shot) || Object.keys(shot).some(k => !['id','startFrame','endFrame','title','subject','family','camera','strength','lighting','transition','diagram'].includes(k))) fail();
    if (!text(shot.id,80) || ids.has(shot.id) || !integer(shot.startFrame) || !integer(shot.endFrame) || shot.startFrame !== end || shot.endFrame <= end || shot.endFrame > value.totalFrames) fail();
    if (!text(shot.title,500) || !text(shot.subject,200) || !['process','data','comparison','concept'].includes(shot.family)) fail();
    if (!['legacy','locked','push-in','pull-out','pan-left','pan-right','orbit'].includes(shot.camera) ||
        typeof shot.strength !== 'number' || !Number.isFinite(shot.strength) || shot.strength < 0 || shot.strength > 1 ||
        !['legacy','soft','dramatic'].includes(shot.lighting) || !['legacy','fade','cut','slide'].includes(shot.transition)) fail();
    if (shot.diagram !== undefined) {
      const d=shot.diagram;
      if(!plain(d) || Object.keys(d).some(k=>!['kind','labels'].includes(k)) || !['process','comparison'].includes(d.kind) ||
        !Array.isArray(d.labels) || d.labels.length<2 || d.labels.length>5 || (d.kind==='comparison' && d.labels.length!==2) ||
        d.labels.some(s=>!text(s,48) || !s.trim() || /[\u0000-\u001f]/.test(s))) fail();
    }
    ids.add(shot.id); end = shot.endFrame;
  }
  if (end !== value.totalFrames) fail();
  end = 0;
  for (const caption of value.captions) {
    if (!plain(caption) || Object.keys(caption).some(k => !['startFrame','endFrame','text'].includes(k)) || !integer(caption.startFrame) || !integer(caption.endFrame) || caption.startFrame < end || caption.endFrame <= caption.startFrame || caption.endFrame > value.totalFrames || !text(caption.text,500)) fail();
    end = caption.endFrame;
  }
  return value;
}
