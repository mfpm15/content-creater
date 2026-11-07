const form = document.querySelector('#draftForm');
const statusLine = document.querySelector('#formStatus');
const generateButton = document.querySelector('#generateButton');
const progressBox = document.querySelector('#progress');
let currentSlug = null;
let pollTimer = null;

function toast(message) {
  const el = document.querySelector('#toast');
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.hidden = true; }, 2600);
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Permintaan gagal (${response.status})`);
  return data;
}

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  node.append(...children);
  return node;
}

function setStatus(message, isError = false) {
  statusLine.className = isError ? 'form-status error' : 'form-status';
  statusLine.textContent = message;
}

function setBusy(busy) {
  generateButton.disabled = busy;
}

function showProgress(job) {
  progressBox.hidden = job.status !== 'running';
  const percent = Math.min(100, Math.round((job.done / Math.max(job.total, 1)) * 100));
  document.querySelector('#bar').style.width = `${percent}%`;
  document.querySelector('#progressText').textContent = `${percent}% | ${job.message}`;
}

async function loadOptions() {
  const options = await api('/api/articles/options');
  const typeSelect = document.querySelector('#typeSelect');
  typeSelect.replaceChildren(...options.types.map(item => el('option', { value: item.key }, item.label)));
  typeSelect.value = options.defaultType;
  const modelSelect = document.querySelector('#articleModelSelect');
  const models = Array.isArray(options.models) && options.models.length ? options.models : [
    { id: 'ms/GPT-5.6-Think-Deeper', name: 'GPT-5.6 Think Deeper', tier: 'utama' },
  ];
  modelSelect.replaceChildren(...models.map(model =>
    el('option', { value: model.id }, `${model.name} · ${model.tier}`)));
  modelSelect.value = models.some(model => model.id === options.defaultModel)
    ? options.defaultModel : models[0].id;
  const styleSelect = document.querySelector('#styleSelect');
  styleSelect.replaceChildren(
    el('option', { value: options.randomStyle }, 'Acak (setiap gambar beda gaya)'),
    ...options.styles.map(style => el('option', { value: style }, style)));
  document.querySelector('#wordsInput').max = options.limits.maxWords;
  document.querySelector('#imageCount').max = options.limits.maxImages;
}

function renderArticle(article) {
  currentSlug = article.slug;
  document.querySelector('#emptyState').hidden = true;
  document.querySelector('#result').hidden = false;
  document.querySelector('#resultTitle').textContent = article.title;
  document.querySelector('#resultSummary').textContent = article.summary;
  const resumeBox = document.querySelector('#resumeBox');
  const complete = document.querySelector('#complete');
  resumeBox.hidden = article.complete;
  complete.hidden = !article.complete;
  if (!article.complete) {
    document.querySelector('#resumeText').textContent =
      `Belum selesai: ${article.sectionsDone}/${article.sectionsTotal || '?'} bagian tersimpan. Bagian yang sudah jadi tidak ditulis ulang.`;
    return;
  }
  document.querySelector('#resultPath').textContent =
    `${article.wordCount.toLocaleString('id-ID')} kata | ${article.referencesCount} rujukan | Folder: ${article.path}`;
  const report = document.querySelector('#writingReport');
  report.hidden = !article.writing;
  if (article.writing) {
    const notes = article.writing.findings.map(f => el('li', {}, f.msg));
    report.replaceChildren(
      el('strong', {}, `Gaya tulisan: ${article.writing.score}/100`),
      el('span', {}, ' (heuristik pola, bukan hasil detektor AI)'),
      ...(notes.length ? [el('ul', {}, ...notes)] : [el('span', {}, ' | tidak ada pola yang perlu dirapikan')]));
  }
  document.querySelector('#mdPreview').textContent = article.markdown;
  renderArticleTools(article);

  document.querySelector('#downloads').replaceChildren(...article.files.map(name =>
    el('a', { href: `/api/articles/${article.slug}/files/${name}`, download: name }, `Unduh ${name}`)));

  const list = document.querySelector('#imageList');
  if (!article.images.length) {
    list.replaceChildren(el('p', { className: 'muted small' }, 'Artikel ini tidak meminta gambar.'));
    return;
  }
  list.replaceChildren(...article.images.map(image => {
    const badge = el('span', { className: `badge${image.hasFile ? ' ok' : ''}` }, image.hasFile ? 'gambar terpasang' : 'belum ada gambar');
    const copy = el('button', { type: 'button' }, 'Salin prompt');
    copy.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(image.prompt); toast('Prompt disalin'); }
      catch { toast('Gagal menyalin; blok teks lalu salin manual'); }
    });
    const file = el('input', { type: 'file', accept: 'image/png,image/jpeg' });
    file.addEventListener('change', () => upload(image.id, file));
    return el('article', { className: 'image-card' },
      el('header', {}, el('strong', {}, image.id), badge),
      el('div', { className: 'muted small' }, `${image.purpose || '-'} | rasio ${image.aspect}`),
      el('div', { className: 'muted small' }, `Gaya: ${image.style || '-'}`),
      el('pre', {}, image.prompt),
      el('div', { className: 'actions' }, copy, file));
  }));
}

async function upload(imageId, input) {
  const file = input.files[0];
  if (!file || !currentSlug) return;
  try {
    renderArticle(await api(`/api/articles/${currentSlug}/images/${encodeURIComponent(imageId)}`, {
      method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: await file.arrayBuffer(),
    }));
    toast('Gambar terpasang, dokumen dibangun ulang');
  } catch (error) {
    input.value = '';
    toast(error.message);
  }
}

function watch(jobId) {
  clearTimeout(pollTimer);
  setBusy(true);
  const tick = async () => {
    try {
      const job = await api(`/api/articles/jobs/${encodeURIComponent(jobId)}`);
      currentSlug = job.slug;
      showProgress(job);
      if (job.status === 'running') { pollTimer = setTimeout(tick, 2000); return; }
      setBusy(false);
      progressBox.hidden = true;
      renderArticle(await api(`/api/articles/${job.slug}`));
      loadHistory();
      if (job.status === 'done') setStatus('Selesai.');
      else setStatus(job.error || 'Gagal.', true);
    } catch (error) {
      setBusy(false);
      progressBox.hidden = true;
      setStatus(error.message, true);
    }
  };
  tick();
}

async function resume(slug) {
  try {
    setStatus('Melanjutkan...');
    const job = await api(`/api/articles/${encodeURIComponent(slug)}/resume`, { method: 'POST' });
    watch(job.id);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function loadHistory() {
  const { articles } = await api('/api/articles');
  const history = document.querySelector('#history');
  if (!articles.length) { history.replaceChildren(el('li', {}, 'Belum ada.')); return; }
  history.replaceChildren(...articles.map(item => {
    let label = 'Buka';
    let action = async () => renderArticle(await api(`/api/articles/${item.slug}`));
    if (!item.complete && item.job) { label = 'Pantau'; action = async () => watch(item.job); }
    else if (!item.complete) { label = 'Lanjutkan'; action = async () => resume(item.slug); }
    const button = el('button', { type: 'button' }, label);
    button.addEventListener('click', async () => {
      try { await action(); if (label === 'Buka') window.scrollTo({ top: 0, behavior: 'smooth' }); }
      catch (error) { toast(error.message); }
    });
    return el('li', {}, el('span', {}, item.complete ? item.title : `${item.title} (belum selesai)`), button);
  }));
}

document.querySelector('#resumeButton').addEventListener('click', () => currentSlug && resume(currentSlug));

form.addEventListener('submit', async event => {
  event.preventDefault();
  setBusy(true);
  setStatus('Memulai...');
  try {
    const job = await api('/api/articles', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.fromEntries(new FormData(form))),
    });
    setStatus('Artikel ditulis di latar belakang. Halaman ini boleh ditutup lalu dibuka lagi; lihat Artikel sebelumnya.');
    loadHistory();
    watch(job.id);
  } catch (error) {
    setBusy(false);
    setStatus(error.message, true);
  }
});

loadOptions().then(loadHistory).catch(error => {
  const modelSelect = document.querySelector('#articleModelSelect');
  if (modelSelect && !modelSelect.options.length) {
    modelSelect.replaceChildren(el('option', { value: 'ms/GPT-5.6-Think-Deeper' }, 'GPT-5.6 Think Deeper · utama'));
  }
  toast(`Opsi gagal dimuat: ${error.message}. Muat ulang halaman.`);
});

function renderArticleTools(article) {
  const root=document.getElementById('articleTools');root.replaceChildren();
  const send=async(action,body)=>api(`/api/articles/${encodeURIComponent(article.slug)}/${action}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const refresh=async()=>renderArticle(await api(`/api/articles/${encodeURIComponent(article.slug)}`));
  const report=article.evidence;
  const evidencePanel=el('details',{},el('summary',{},`Bukti & klaim: ${report.unreviewed} paragraf perlu review · ${report.diagnostics?.claims_with_warnings || 0} peringatan angka/sitasi`));
  evidencePanel.append(el('p',{},'Kutipan dan sitasi tidak otomatis membuktikan fakta. Pemeriksaan di sini adalah catatan review pengguna, bukan fact-check otomatis.'));
  if(report.diagnostics){
    const diagnostics=report.diagnostics;
    evidencePanel.append(el('p',{},`${diagnostics.claims_with_warnings} paragraf memiliki peringatan angka/sitasi. Angka dibandingkan secara literal dengan kutipan sumber tertaut; kesamaan angka tidak membuktikan makna, satuan, atau kebenaran.`));
    if(diagnostics.uncited_references.length)evidencePanel.append(el('p',{},`Rujukan belum disitasi: ${diagnostics.uncited_references.join(', ')}`));
    if(diagnostics.duplicate_reference_groups.length)evidencePanel.append(el('p',{},`Rujukan berulang: ${diagnostics.duplicate_reference_groups.map(group=>group.join(', ')).join('; ')}`));
    const warnings=report.claims.filter(item=>item.review_warnings?.length);
    for(const item of warnings.slice(0,100))evidencePanel.append(el('p',{},`Blok ${item.block+1}: ${item.review_warnings.join('. ')}. Klaim: ${item.text.slice(0,180)}`));
    if(warnings.length>100)evidencePanel.append(el('p',{},`${warnings.length-100} peringatan lainnya tersedia dalam laporan API.`));
  }
  const url=el('input',{placeholder:'URL HTTPS sumber'}),title=el('input',{placeholder:'Judul sumber'}),quote=el('textarea',{placeholder:'Kutipan bukti yang Anda periksa'}),date=el('input',{type:'date'}),add=el('button',{type:'button'},'Tambahkan sumber');
  add.onclick=async()=>{try{await send('evidence',{revision:report.revision,action:'source',url:url.value,title:title.value,excerpt:quote.value,published_at:date.value});await refresh()}catch(error){toast(error.message)}};
  const fetchSource=el('button',{type:'button'},'Ambil teks publik (host harus diizinkan)');
  fetchSource.onclick=async()=>{fetchSource.disabled=true;try{const data=await api('/api/articles/source',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:url.value})});quote.value=data.excerpt;if(data.published_at)date.value=data.published_at.slice(0,10);toast('Teks diambil; periksa kutipan dan tanggal sebelum disimpan')}catch(error){toast(error.message)}finally{fetchSource.disabled=false}};
  evidencePanel.append(el('div',{},url,title,quote,date,fetchSource,add));
  const source=el('select',{},...report.sources.map(item=>el('option',{value:item.id},`${item.title||item.url} ${item.verified?'— sudah direview':'— belum direview'}`))),note=el('input',{placeholder:'Catatan pemeriksaan (minimal 10 karakter)'}),verify=el('button',{type:'button'},'Saya sudah memeriksa sumber & kutipan');
  verify.onclick=async()=>{try{await send('evidence',{revision:report.revision,action:'verify',source_id:source.value,note:note.value});await refresh()}catch(error){toast(error.message)}};
  const sourceDetail=el('pre',{});
  const showSource=()=>{const row=report.sources.find(item=>item.id===source.value);sourceDetail.textContent=row?`${row.url}\nTanggal: ${row.published_at||'Tidak diketahui'}\n${row.excerpt}\n${row.review_note||''}`:''};source.onchange=showSource;showSource();
  evidencePanel.append(el('div',{},source,sourceDetail,note,verify));
  const claim=el('select',{},...report.claims.map(item=>el('option',{value:item.id},`${item.status}: ${item.text.slice(0,90)}`))),link=el('button',{type:'button'},'Hubungkan klaim ke sumber terpilih');
  link.onclick=async()=>{try{await send('evidence',{revision:report.revision,action:'link',claim_id:claim.value,source_ids:[source.value]});await refresh()}catch(error){toast(error.message)}};
  evidencePanel.append(el('div',{},claim,link));root.append(evidencePanel);
  const rewritePanel=el('details',{},el('summary',{},'Revisi bagian dengan review sebelum diterapkan'));
  const section=el('select',{},...article.sections.map(item=>el('option',{value:item.index},item.heading))),instruction=el('textarea',{placeholder:'Instruksi perbaikan bahasa; jangan ubah fakta'}),propose=el('button',{type:'button'},'Buat usulan revisi'),comparison=el('div',{});
  propose.onclick=async()=>{propose.disabled=true;try{
    const result=await send('rewrite',{article_revision:article.article_revision,section:Number(section.value),instruction:instruction.value});
    const apply=el('button',{type:'button'},'Setujui & terapkan revisi ini');
    comparison.replaceChildren(el('h4',{},'Sebelum'),el('pre',{},result.before.join('\n\n')),el('h4',{},'Usulan — periksa makna dan nama sebelum menyetujui'),el('pre',{},result.after.join('\n\n')),apply);
    apply.onclick=async()=>{apply.disabled=true;try{renderArticle(await send('apply-rewrite',{proposal_id:result.id,approve:true}))}catch(error){toast(error.message);apply.disabled=false}};
  }catch(error){toast(error.message)}finally{propose.disabled=false}};
  rewritePanel.append(section,instruction,propose,comparison);
  for(const proposal of article.rewrite_proposals||[]){
    const show=el('button',{type:'button'},proposal.stale?'Usulan lama (artikel telah berubah)':'Buka usulan tersimpan');show.disabled=proposal.stale;
    show.onclick=()=>{const apply=el('button',{type:'button'},'Setujui & terapkan usulan tersimpan');comparison.replaceChildren(el('h4',{},'Sebelum'),el('pre',{},proposal.before.join('\n\n')),el('h4',{},'Usulan — periksa makna dan nama'),el('pre',{},proposal.after.join('\n\n')),apply);apply.onclick=async()=>{apply.disabled=true;try{renderArticle(await send('apply-rewrite',{proposal_id:proposal.id,approve:true}))}catch(error){toast(error.message);apply.disabled=false}}};rewritePanel.append(show);
  }
  root.append(rewritePanel);
  if(article.improvements){
    const plan=el('details',{},el('summary',{},`Rencana perbaikan otomatis: ${article.improvements.sections.length} bagian`));
    plan.append(el('p',{},'Prioritas berasal dari pemeriksaan lokal. Saran bahasa dibuat sebagai usulan; fakta/sumber harus diperiksa dan perubahan memerlukan persetujuan Anda.'));
    for(const item of article.improvements.sections){
      const row=el('div',{},el('h4',{},item.heading),el('p',{},`${item.source_checks} paragraf perlu pemeriksaan sumber. ${item.language_findings.join('. ')}`));
      if(item.can_propose_language){
        const button=el('button',{type:'button'},'Usulkan perbaikan bahasa bagian ini');
        button.onclick=()=>{section.value=String(item.section);instruction.value=item.instruction;rewritePanel.open=true;propose.click();rewritePanel.scrollIntoView({block:'center'})};
        row.append(button);
      }
      plan.append(row);
    }
    root.append(plan);
  }
  const diagramPanel=el('details',{},el('summary',{},'Diagram lokal → SVG, PNG, dan Word'));
  const kind=el('select',{},el('option',{value:'flow'},'Alur berurutan'),el('option',{value:'mindmap'},'Mind map satu tingkat')),
    labels=el('textarea',{placeholder:'Satu label per baris, maksimal 60 karakter. Mind map: baris pertama adalah pusat.'}),diagramTitle=el('input',{placeholder:'Judul diagram'}),diagram=el('button',{type:'button'},'Buat dan sisipkan diagram');
  diagram.onclick=async()=>{diagram.disabled=true;try{renderArticle(await send('diagram',{article_revision:article.article_revision,kind:kind.value,labels:labels.value.split('\n').map(x=>x.trim()).filter(Boolean),title:diagramTitle.value}))}catch(error){toast(error.message)}finally{diagram.disabled=false}};
  diagramPanel.append(kind,diagramTitle,labels,diagram);root.append(diagramPanel);
}
