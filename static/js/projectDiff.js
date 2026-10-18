// Pure helpers shared by Projects UI and Node regression tests.
export function terminalMode(text) { return typeof text === 'string' && text.startsWith('!'); }
export function fileReferences(text) {
  const found = [];
  for (const m of String(text || '').matchAll(/@\{([^}\r\n]+)\}|(?:^|\s)@([^\s@{}]+)/g)) found.push(m[1] || m[2]);
  return [...new Set(found)];
}
export function alignDiff(before, after) {
  const allA = before === '' ? [] : before.split('\n');
  const allB = after === '' ? [] : after.split('\n');
  const a=allA.slice(0,5001),b=allB.slice(0,5001);
  const inputClipped=allA.length>5000||allB.length>5000;
  const rows = [];
  const push = (i, j, kind) => rows.push({left:i===null?null:{line:i+1,text:a[i],kind},right:j===null?null:{line:j+1,text:b[j],kind}});
  let prefix=0;
  while(prefix<a.length&&prefix<b.length&&a[prefix]===b[prefix]) {push(prefix,prefix,'same');prefix++;}
  let ae=a.length,be=b.length;
  while(ae>prefix&&be>prefix&&a[ae-1]===b[be-1]) {ae--;be--;}
  const n=ae-prefix,m=be-prefix,approximate=n*m>1000000;
  if(approximate) {
    for(let k=0;k<Math.max(n,m);k++) push(k<n?prefix+k:null,k<m?prefix+k:null,'changed');
  } else {
    const dp=Array.from({length:n+1},()=>new Uint32Array(m+1));
    for(let i=n-1;i>=0;i--)for(let j=m-1;j>=0;j--)dp[i][j]=a[prefix+i]===b[prefix+j]?dp[i+1][j+1]+1:Math.max(dp[i+1][j],dp[i][j+1]);
    let i=0,j=0;
    while(i<n||j<m) {
      if(i<n&&j<m&&a[prefix+i]===b[prefix+j]) {push(prefix+i++,prefix+j++,'same');}
      else if(j<m&&(i===n||dp[i][j+1]>dp[i+1][j])) {push(null,prefix+j++,'added');}
      else {push(prefix+i++,null,'deleted');}
    }
  }
  for(let k=0;k<a.length-ae;k++)push(ae+k,be+k,'same');
  const aligned=[];
  for(let k=0;k<rows.length;) {
    if(rows[k].left?.kind==='same'||rows[k].right?.kind==='same'){aligned.push(rows[k++]);continue;}
    const left=[],right=[];
    while(k<rows.length&&rows[k].left?.kind!=='same'&&rows[k].right?.kind!=='same') {
      if(rows[k].left)left.push(rows[k].left);
      if(rows[k].right)right.push(rows[k].right);
      k++;
    }
    for(let i=0;i<Math.max(left.length,right.length);i++)aligned.push({left:left[i]||null,right:right[i]||null});
  }
  return {rows:aligned.slice(0,5000),truncated:inputClipped||aligned.length>5000,approximate};
}
