var j=globalThis,W=j.ShadowRoot&&(j.ShadyCSS===void 0||j.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,oe=Symbol(),xe=new WeakMap,N=class{constructor(e,s,i){if(this._$cssResult$=!0,i!==oe)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=s}get styleSheet(){let e=this.o,s=this.t;if(W&&e===void 0){let i=s!==void 0&&s.length===1;i&&(e=xe.get(s)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&xe.set(s,e))}return e}toString(){return this.cssText}},we=t=>new N(typeof t=="string"?t:t+"",void 0,oe),v=(t,...e)=>{let s=t.length===1?t[0]:e.reduce((i,r,n)=>i+(o=>{if(o._$cssResult$===!0)return o.cssText;if(typeof o=="number")return o;throw Error("Value passed to 'css' function must be a 'css' function result: "+o+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(r)+t[n+1],t[0]);return new N(s,t,oe)},ke=(t,e)=>{if(W)t.adoptedStyleSheets=e.map(s=>s instanceof CSSStyleSheet?s:s.styleSheet);else for(let s of e){let i=document.createElement("style"),r=j.litNonce;r!==void 0&&i.setAttribute("nonce",r),i.textContent=s.cssText,t.appendChild(i)}},ae=W?t=>t:t=>t instanceof CSSStyleSheet?(e=>{let s="";for(let i of e.cssRules)s+=i.cssText;return we(s)})(t):t;var{is:dt,defineProperty:ct,getOwnPropertyDescriptor:ht,getOwnPropertyNames:ut,getOwnPropertySymbols:pt,getPrototypeOf:mt}=Object,F=globalThis,Se=F.trustedTypes,gt=Se?Se.emptyScript:"",ft=F.reactiveElementPolyfillSupport,O=(t,e)=>t,ne={toAttribute(t,e){switch(e){case Boolean:t=t?gt:null;break;case Object:case Array:t=t==null?t:JSON.stringify(t)}return t},fromAttribute(t,e){let s=t;switch(e){case Boolean:s=t!==null;break;case Number:s=t===null?null:Number(t);break;case Object:case Array:try{s=JSON.parse(t)}catch{s=null}}return s}},Ee=(t,e)=>!dt(t,e),Ae={attribute:!0,type:String,converter:ne,reflect:!1,useDefault:!1,hasChanged:Ee};Symbol.metadata??=Symbol("metadata"),F.litPropertyMetadata??=new WeakMap;var $=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,s=Ae){if(s.state&&(s.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((s=Object.create(s)).wrapped=!0),this.elementProperties.set(e,s),!s.noAccessor){let i=Symbol(),r=this.getPropertyDescriptor(e,i,s);r!==void 0&&ct(this.prototype,e,r)}}static getPropertyDescriptor(e,s,i){let{get:r,set:n}=ht(this.prototype,e)??{get(){return this[s]},set(o){this[s]=o}};return{get:r,set(o){let c=r?.call(this);n?.call(this,o),this.requestUpdate(e,c,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??Ae}static _$Ei(){if(this.hasOwnProperty(O("elementProperties")))return;let e=mt(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(O("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(O("properties"))){let s=this.properties,i=[...ut(s),...pt(s)];for(let r of i)this.createProperty(r,s[r])}let e=this[Symbol.metadata];if(e!==null){let s=litPropertyMetadata.get(e);if(s!==void 0)for(let[i,r]of s)this.elementProperties.set(i,r)}this._$Eh=new Map;for(let[s,i]of this.elementProperties){let r=this._$Eu(s,i);r!==void 0&&this._$Eh.set(r,s)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let s=[];if(Array.isArray(e)){let i=new Set(e.flat(1/0).reverse());for(let r of i)s.unshift(ae(r))}else e!==void 0&&s.push(ae(e));return s}static _$Eu(e,s){let i=s.attribute;return i===!1?void 0:typeof i=="string"?i:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,s=this.constructor.elementProperties;for(let i of s.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return ke(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,s,i){this._$AK(e,i)}_$ET(e,s){let i=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,i);if(r!==void 0&&i.reflect===!0){let n=(i.converter?.toAttribute!==void 0?i.converter:ne).toAttribute(s,i.type);this._$Em=e,n==null?this.removeAttribute(r):this.setAttribute(r,n),this._$Em=null}}_$AK(e,s){let i=this.constructor,r=i._$Eh.get(e);if(r!==void 0&&this._$Em!==r){let n=i.getPropertyOptions(r),o=typeof n.converter=="function"?{fromAttribute:n.converter}:n.converter?.fromAttribute!==void 0?n.converter:ne;this._$Em=r;let c=o.fromAttribute(s,n.type);this[r]=c??this._$Ej?.get(r)??c,this._$Em=null}}requestUpdate(e,s,i,r=!1,n){if(e!==void 0){let o=this.constructor;if(r===!1&&(n=this[e]),i??=o.getPropertyOptions(e),!((i.hasChanged??Ee)(n,s)||i.useDefault&&i.reflect&&n===this._$Ej?.get(e)&&!this.hasAttribute(o._$Eu(e,i))))return;this.C(e,s,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,s,{useDefault:i,reflect:r,wrapped:n},o){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,o??s??this[e]),n!==!0||o!==void 0)||(this._$AL.has(e)||(this.hasUpdated||i||(s=void 0),this._$AL.set(e,s)),r===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(s){Promise.reject(s)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[r,n]of this._$Ep)this[r]=n;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[r,n]of i){let{wrapped:o}=n,c=this[r];o!==!0||this._$AL.has(r)||c===void 0||this.C(r,void 0,n,c)}}let e=!1,s=this._$AL;try{e=this.shouldUpdate(s),e?(this.willUpdate(s),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(s)):this._$EM()}catch(i){throw e=!1,this._$EM(),i}e&&this._$AE(s)}willUpdate(e){}_$AE(e){this._$EO?.forEach(s=>s.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(s=>this._$ET(s,this[s])),this._$EM()}updated(e){}firstUpdated(e){}};$.elementStyles=[],$.shadowRootOptions={mode:"open"},$[O("elementProperties")]=new Map,$[O("finalized")]=new Map,ft?.({ReactiveElement:$}),(F.reactiveElementVersions??=[]).push("2.1.2");var me=globalThis,Le=t=>t,Z=me.trustedTypes,De=Z?Z.createPolicy("lit-html",{createHTML:t=>t}):void 0,Ne="$lit$",k=`lit$${Math.random().toFixed(9).slice(2)}$`,Oe="?"+k,_t=`<${Oe}>`,R=document,U=()=>R.createComment(""),I=t=>t===null||typeof t!="object"&&typeof t!="function",ge=Array.isArray,yt=t=>ge(t)||typeof t?.[Symbol.iterator]=="function",le=`[ 	
\f\r]`,P=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Re=/-->/g,Ce=/>/g,L=RegExp(`>|${le}(?:([^\\s"'>=/]+)(${le}*=${le}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Te=/'/g,Me=/"/g,Pe=/^(?:script|style|textarea|title)$/i,fe=t=>(e,...s)=>({_$litType$:t,strings:e,values:s}),a=fe(1),b=fe(2),Nt=fe(3),C=Symbol.for("lit-noChange"),l=Symbol.for("lit-nothing"),ze=new WeakMap,D=R.createTreeWalker(R,129);function Ue(t,e){if(!ge(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return De!==void 0?De.createHTML(e):e}var bt=(t,e)=>{let s=t.length-1,i=[],r,n=e===2?"<svg>":e===3?"<math>":"",o=P;for(let c=0;c<s;c++){let d=t[c],h,u,p=-1,m=0;for(;m<d.length&&(o.lastIndex=m,u=o.exec(d),u!==null);)m=o.lastIndex,o===P?u[1]==="!--"?o=Re:u[1]!==void 0?o=Ce:u[2]!==void 0?(Pe.test(u[2])&&(r=RegExp("</"+u[2],"g")),o=L):u[3]!==void 0&&(o=L):o===L?u[0]===">"?(o=r??P,p=-1):u[1]===void 0?p=-2:(p=o.lastIndex-u[2].length,h=u[1],o=u[3]===void 0?L:u[3]==='"'?Me:Te):o===Me||o===Te?o=L:o===Re||o===Ce?o=P:(o=L,r=void 0);let y=o===L&&t[c+1].startsWith("/>")?" ":"";n+=o===P?d+_t:p>=0?(i.push(h),d.slice(0,p)+Ne+d.slice(p)+k+y):d+k+(p===-2?c:y)}return[Ue(t,n+(t[s]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),i]},q=class t{constructor({strings:e,_$litType$:s},i){let r;this.parts=[];let n=0,o=0,c=e.length-1,d=this.parts,[h,u]=bt(e,s);if(this.el=t.createElement(h,i),D.currentNode=this.el.content,s===2||s===3){let p=this.el.content.firstChild;p.replaceWith(...p.childNodes)}for(;(r=D.nextNode())!==null&&d.length<c;){if(r.nodeType===1){if(r.hasAttributes())for(let p of r.getAttributeNames())if(p.endsWith(Ne)){let m=u[o++],y=r.getAttribute(p).split(k),f=/([.?@])?(.*)/.exec(m);d.push({type:1,index:n,name:f[2],strings:y,ctor:f[1]==="."?ce:f[1]==="?"?he:f[1]==="@"?ue:M}),r.removeAttribute(p)}else p.startsWith(k)&&(d.push({type:6,index:n}),r.removeAttribute(p));if(Pe.test(r.tagName)){let p=r.textContent.split(k),m=p.length-1;if(m>0){r.textContent=Z?Z.emptyScript:"";for(let y=0;y<m;y++)r.append(p[y],U()),D.nextNode(),d.push({type:2,index:++n});r.append(p[m],U())}}}else if(r.nodeType===8)if(r.data===Oe)d.push({type:2,index:n});else{let p=-1;for(;(p=r.data.indexOf(k,p+1))!==-1;)d.push({type:7,index:n}),p+=k.length-1}n++}}static createElement(e,s){let i=R.createElement("template");return i.innerHTML=e,i}};function T(t,e,s=t,i){if(e===C)return e;let r=i!==void 0?s._$Co?.[i]:s._$Cl,n=I(e)?void 0:e._$litDirective$;return r?.constructor!==n&&(r?._$AO?.(!1),n===void 0?r=void 0:(r=new n(t),r._$AT(t,s,i)),i!==void 0?(s._$Co??=[])[i]=r:s._$Cl=r),r!==void 0&&(e=T(t,r._$AS(t,e.values),r,i)),e}var de=class{constructor(e,s){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=s}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:s},parts:i}=this._$AD,r=(e?.creationScope??R).importNode(s,!0);D.currentNode=r;let n=D.nextNode(),o=0,c=0,d=i[0];for(;d!==void 0;){if(o===d.index){let h;d.type===2?h=new B(n,n.nextSibling,this,e):d.type===1?h=new d.ctor(n,d.name,d.strings,this,e):d.type===6&&(h=new pe(n,this,e)),this._$AV.push(h),d=i[++c]}o!==d?.index&&(n=D.nextNode(),o++)}return D.currentNode=R,r}p(e){let s=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(e,i,s),s+=i.strings.length-2):i._$AI(e[s])),s++}},B=class t{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,s,i,r){this.type=2,this._$AH=l,this._$AN=void 0,this._$AA=e,this._$AB=s,this._$AM=i,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,s=this._$AM;return s!==void 0&&e?.nodeType===11&&(e=s.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,s=this){e=T(this,e,s),I(e)?e===l||e==null||e===""?(this._$AH!==l&&this._$AR(),this._$AH=l):e!==this._$AH&&e!==C&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):yt(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==l&&I(this._$AH)?this._$AA.nextSibling.data=e:this.T(R.createTextNode(e)),this._$AH=e}$(e){let{values:s,_$litType$:i}=e,r=typeof i=="number"?this._$AC(e):(i.el===void 0&&(i.el=q.createElement(Ue(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===r)this._$AH.p(s);else{let n=new de(r,this),o=n.u(this.options);n.p(s),this.T(o),this._$AH=n}}_$AC(e){let s=ze.get(e.strings);return s===void 0&&ze.set(e.strings,s=new q(e)),s}k(e){ge(this._$AH)||(this._$AH=[],this._$AR());let s=this._$AH,i,r=0;for(let n of e)r===s.length?s.push(i=new t(this.O(U()),this.O(U()),this,this.options)):i=s[r],i._$AI(n),r++;r<s.length&&(this._$AR(i&&i._$AB.nextSibling,r),s.length=r)}_$AR(e=this._$AA.nextSibling,s){for(this._$AP?.(!1,!0,s);e!==this._$AB;){let i=Le(e).nextSibling;Le(e).remove(),e=i}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},M=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,s,i,r,n){this.type=1,this._$AH=l,this._$AN=void 0,this.element=e,this.name=s,this._$AM=r,this.options=n,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=l}_$AI(e,s=this,i,r){let n=this.strings,o=!1;if(n===void 0)e=T(this,e,s,0),o=!I(e)||e!==this._$AH&&e!==C,o&&(this._$AH=e);else{let c=e,d,h;for(e=n[0],d=0;d<n.length-1;d++)h=T(this,c[i+d],s,d),h===C&&(h=this._$AH[d]),o||=!I(h)||h!==this._$AH[d],h===l?e=l:e!==l&&(e+=(h??"")+n[d+1]),this._$AH[d]=h}o&&!r&&this.j(e)}j(e){e===l?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},ce=class extends M{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===l?void 0:e}},he=class extends M{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==l)}},ue=class extends M{constructor(e,s,i,r,n){super(e,s,i,r,n),this.type=5}_$AI(e,s=this){if((e=T(this,e,s,0)??l)===C)return;let i=this._$AH,r=e===l&&i!==l||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,n=e!==l&&(i===l||r);r&&this.element.removeEventListener(this.name,this,i),n&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},pe=class{constructor(e,s,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=s,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){T(this,e)}};var vt=me.litHtmlPolyfillSupport;vt?.(q,B),(me.litHtmlVersions??=[]).push("3.3.3");var Ie=(t,e,s)=>{let i=s?.renderBefore??e,r=i._$litPart$;if(r===void 0){let n=s?.renderBefore??null;i._$litPart$=r=new B(e.insertBefore(U(),n),n,void 0,s??{})}return r._$AI(t),r};var _e=globalThis,S=class extends ${constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let s=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Ie(s,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return C}};S._$litElement$=!0,S.finalized=!0,_e.litElementHydrateSupport?.({LitElement:S});var $t=_e.litElementPolyfillSupport;$t?.({LitElement:S});(_e.litElementVersions??=[]).push("4.2.2");function K(t,e,s,i){return a`<dialog aria-labelledby="detail-title" @cancel=${()=>t._closeDetail()}>
    <div class="detail-header"><div><p class="eyebrow">${s}</p><h2 id="detail-title">${e}</h2></div><button autofocus @click=${()=>t._closeDetail()}>Close</button></div>
    ${i}
  </dialog>`}function ye(t,e=!1){let s=t.points;if(!s.length)return a`<div class="trend-empty">No readings in the last 14 days</div>`;let i=e?600:160,r=e?150:48,n=s.map(f=>f.v),o=Math.min(...n),c=Math.max(...n)-o||Math.abs(o)*.05||1,d=s.map(f=>new Date(f.t).getTime()),h=d[d.length-1]-d[0]||1,u=f=>6+(d[f]-d[0])/h*(i-12),p=f=>r-8-(f-o)/c*(r-16),m=[],y="";return s.forEach((f,E)=>{E&&f.source_changed&&(m.push(y),y=""),y+=`${y?" L":"M"}${u(E)},${p(f.v)}`}),m.push(y),a`<svg class="sparkline" viewBox="0 0 ${i} ${r}" role="img" aria-label="Recorded trend over 14 days. Lines break when the source changes.">
    ${m.map(f=>b`<path d=${f}></path>`)}
    ${s.map((f,E)=>b`<circle cx=${u(E)} cy=${p(f.v)} r=${e?2.5:1.8}><title>${f.v} ${t.unit} · ${new Date(f.t).toLocaleString()}</title></circle>`)}
  </svg>`}function H(t,e){if(e.state==="source_changed")return"Source changed. Compare with care.";if(e.state==="conflict")return"Sources disagree. Review readings.";if(e.delta===null)return"More history needed for a comparison";let s=t._display(Math.abs(e.delta),e.unit),i=e.unit==="count"?0:1;if(Number(s.value.toFixed(i))===0)return"No visible change at this precision";let r=s.unit==="count"?"steps":s.unit==="%"?"percentage points":s.unit;return`${e.delta>0?"+":e.delta<0?"\u2212":""}${t._fmt(s.value,i)} ${r} \xB7 ${e.state==="steady"?"little change":e.delta>0?"up":"down"}`}function Be(t,e){let s=e.current;return s?`${e.stale?"Older reading \xB7 ":"Observed "}${t._when(s.observed_at)}`:"No readings yet"}function qe(t,e){return a`<button class="metric-row ${e.stale?"stale":""}" @click=${s=>t._openDetail(e.metric,s)}>
    <div><span class="metric-name">${t._label(e.metric)}</span><span class="metric-source">${e.current?t._providerName(e.current.provider):"Connect a source or log a reading"}</span></div>
    <div class="row-trend">${ye(e)}</div>
    <div class="metric-value">${t._metricValue(e.current,e.unit==="count"?0:1)}<span class="metric-source">${Be(t,e)}</span></div>
    <div class="row-change">${e.current?H(t,e):"No comparison yet"}${e.delta!==null?a`<span class="metric-source">${e.comparison_label}</span>`:l}</div>
    <span class="row-arrow" aria-hidden="true">›</span>
  </button>`}function He(t){let e=t._overview;if(!e)return a`<p role="status">${t._loading?"Loading your health record\u2026":"Health data is unavailable."}</p>`;let s=e.metrics.filter(o=>o.current),i=s[0],r=s.filter(o=>o!==i),n=e.metrics.filter(o=>!o.current);return a`
    <div class="overview-actions"><button @click=${()=>t._openForm("measure")}>Log a measurement</button><button @click=${()=>t._openForm("workout")}>Log a workout</button></div>
    ${t._measurementForm()}${t._workoutForm()}
    ${i?a`<section class="lead-change ${i.stale?"stale":""}">
      <div class="lead-copy"><p class="eyebrow">${i.state==="changed"&&!i.stale?"A change in your record":i.state==="conflict"?"Worth a closer look":"Your latest readings"}</p>
        <h2>${t._label(i.metric)}</h2><div class="lead-value">${t._metricValue(i.current,i.unit==="count"?0:1)}</div>
        <p class="change-line">${H(t,i)}</p>
        ${i.delta!==null?a`<p class="sub">${i.comparison_label}</p>`:l}
        <p class="sub">${t._providerName(i.current.provider)} · ${Be(t,i)}</p>
        <button class="primary" @click=${o=>t._openDetail(i.metric,o)}>Review ${t._label(i.metric).toLowerCase()}</button>
      </div><div class="lead-chart">${ye(i,!0)}<span class="sub">Last 14 days · recorded readings</span></div>
    </section>`:a`<section class="intro-empty"><p class="eyebrow">Start with one reading</p><h2>Your health record starts here.</h2><p>Connect your scale or activity tracker in Health Assistant’s integration settings, or log a measurement above. Your history stays on this Home Assistant instance.</p><a href="/config/integrations/integration/health_assistant">Open integration settings</a></section>`}
    ${r.length?a`<section class="metric-section" aria-label="Health metrics"><div class="section-heading"><h2>The rest of your record</h2><span class="sub">Select a metric for readings and sources</span></div>${r.map(o=>qe(t,o))}</section>`:l}
    ${n.length?a`<details class="missing-metrics"><summary>${n.length} ${n.length===1?"metric":"metrics"} without readings</summary><p class="sub">Connect a source, add a reading, or open a metric to restore an excluded record.</p>${n.map(o=>qe(t,o))}</details>`:l}
    <section class="workout-section"><div class="section-heading"><h2>This week’s training</h2><span class="sub">${e.workout_count} ${e.workout_count===1?"workout":"workouts"} in the last 7 days</span></div>
      ${e.workouts.length?a`<div class="workout-strip">${e.workouts.map(o=>a`<article class="workout-item"><span class="eyebrow">${t._when(o.started_at)}</span><h3>${o.title}</h3><p>${t._fmt(o.duration_seconds/60,0)} min · ${o.workout_type}</p><span class="sub">${t._providerName(o.provider)}</span></article>`)}</div>`:a`<p class="empty-note">No workouts recorded this week. Connected workout sources and manual entries will appear here.</p>`}
    </section>
    <details class="source-status"><summary>Sources <span>${e.providers.filter(o=>o.degraded).length?"\xB7 needs attention":"\xB7 status"}</span></summary><p class="sub">Successful source operations and measurement times are different. A source can be working while its latest reading is old.</p>${e.providers.map(o=>a`<div class="source-row"><strong>${t._providerName(o.key)}</strong><span>${o.degraded?"Needs attention":o.had_error?"Working again":o.last_success?"Working":"Waiting for data"}</span><span class="sub">${o.last_success?`Last successful operation ${t._when(o.last_success)}`:"No successful operation since reload"}</span></div>`)}<a href="/config/integrations/integration/health_assistant">Manage sources in integration settings</a></details>
  `}function Qe(t){if(!t._detailMetric)return l;let e=t._overview?.metrics.find(r=>r.metric===t._detailMetric),s=t._detail,i=s?.observation;return K(t,t._label(t._detailMetric),"Readings and sources",a`
    ${t._detailError?a`<p class="error" role="alert">${t._detailError}<button @click=${()=>t._loadDetail()}>Try again</button></p>`:l}
    ${e?a`<div class="detail-trend">${ye(e,!0)}<p class="sub">${H(t,e)}${e.delta!==null?` \xB7 ${e.comparison_label}`:""}</p></div>`:l}
    ${t._detailLoading?a`<p role="status">Loading readings…</p>`:l}
    ${i?a`<section class="reading-detail"><div class="section-heading"><h3>${i.excluded?"Excluded reading":"Selected reading"}</h3><span class="reading-value">${t._metricValue(i)}</span></div><p>${new Date(i.observed_at).toLocaleString()} · ${t._providerName(i.provider)}</p>
      ${i.possible_duplicate?a`<p class="notice">Nearby sources may disagree. Review the original claims and nearby readings before changing anything.</p>`:l}
      ${i.excluded?a`<p class="notice">Kept in your history, excluded from summaries and trends.</p>`:l}
      <h4>Source claims</h4><p class="sub">The selected claim supplies this record’s value. Source priority resolves equivalent claims; nearby records are shown separately.</p>
      ${s.claims.map(r=>a`<div class="claim-row"><div><strong>${t._providerName(r.provider)}</strong><span class="metric-source">${r.selected?"Selected claim":"Retained claim"} · ${new Date(r.observed_at).toLocaleString()}</span><span class="source-id">${r.external_id}</span></div><span>${t._metricValue(r)}</span></div>`)}
      ${s.claim_count>s.claims.length?a`<p class="sub">Showing ${s.claims.length} of ${s.claim_count} claims.</p>`:l}
      ${s.nearby.length?a`<h4>Nearby readings</h4>${s.nearby.map(r=>a`<button class="record-button" ?disabled=${t._detailLoading} @click=${()=>t._loadDetail(r.id)}><span>${t._providerName(r.provider)} · ${t._when(r.observed_at)}</span><span>${t._metricValue(r)}</span></button>`)}`:l}
      ${t.hass.user?.is_admin?a`<div class="exclusion-control"><p class="sub">${i.excluded?"Restore this reading to summaries and trends.":"An incorrect reading can be excluded without deleting its source history. You can restore it later."}</p><button ?disabled=${!!t._busyId||t._detailLoading} @click=${()=>t._toggleExclusion()}>${t._busyId?"Saving\u2026":i.excluded?"Restore reading":"Exclude reading"}</button></div>`:a`<p class="sub">An administrator can exclude or restore incorrect readings.</p>`}
    </section>`:t._detailLoading?l:a`<p>No ${t._showExcluded?"excluded ":""}readings to show.</p>`}
    <section class="record-history"><div class="section-heading"><h3>Browse readings</h3><label class="excluded-toggle"><input type="checkbox" .checked=${t._showExcluded} @change=${r=>{t._showExcluded=r.target.checked,t._detail=void 0,t._loadDetail()}} /> Excluded only</label></div><p class="sub">Most recently added first</p>
    ${t._records.map(r=>a`<button class="record-button ${i?.id===r.id?"selected":""}" ?disabled=${t._detailLoading} @click=${()=>t._loadDetail(r.id)}><span>${new Date(r.observed_at).toLocaleString()}<span class="metric-source">${t._providerName(r.provider)}</span></span><span>${t._metricValue(r)}</span></button>`)}
    ${t._nextRecord?a`<button ?disabled=${t._detailLoading} @click=${()=>t._loadDetail(i?.id,!0)}>Load older readings</button>`:l}</section>
  `)}var Ve=v`
  :host { --health-line: var(--divider-color, #8885); --health-accent: var(--primary-color, #168c9e); }
  .page-subtitle { margin: 6px 0 0; color: var(--secondary-text-color); font-size: 14px; }
  .header-identity { display: flex; align-items: center; gap: 16px; }
  .overview-actions { display: flex; gap: 8px; margin: 20px 0; flex-wrap: wrap; }
  .lead-change { display: grid; grid-template-columns: minmax(240px, 0.9fr) minmax(0, 1.1fr); gap: 40px; padding: 36px 0 40px; border-top: 1px solid var(--health-line); border-bottom: 1px solid var(--health-line); }
  .lead-copy h2 { font-size: 23px; margin: 12px 0; color: var(--primary-text-color); }
  .eyebrow { font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--secondary-text-color); margin: 0; }
  .lead-value .value { font-size: clamp(42px, 5vw, 64px); line-height: 1.1; font-weight: 500; font-variant-numeric: tabular-nums; }
  .lead-value .unit { font-size: 22px; margin-left: 5px; }
  .change-line { font-size: 16px; margin: 16px 0 4px; }
  .lead-chart { align-self: center; min-width: 0; text-align: right; }
  .lead-copy .sub { text-align: left; font-size: 13px; }
  .sparkline { display: block; width: 100%; overflow: visible; color: var(--health-accent); }
  .sparkline path { fill: none; stroke: currentColor; stroke-width: 2; vector-effect: non-scaling-stroke; }
  .sparkline circle { fill: currentColor; }
  .stale .sparkline { color: var(--secondary-text-color); opacity: 0.65; }
  .stale .metric-value, .stale .lead-value { color: var(--secondary-text-color); }
  .trend-empty { color: var(--secondary-text-color); font-size: 12px; padding: 14px 0; }
  .section-heading { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; margin-bottom: 16px; flex-wrap: wrap; }
  .section-heading h2 { font-size: 19px; color: var(--primary-text-color); margin: 0; }
  .section-heading h3 { margin: 0; }
  .metric-section, .workout-section { margin-top: 32px; }
  .missing-metrics { margin-top: 24px; color: var(--secondary-text-color); }
  .missing-metrics summary { cursor: pointer; padding: 10px 0; font-size: 14px; }
  button.metric-row { width: 100%; display: grid; grid-template-columns: 1.1fr 0.75fr 1fr 1.2fr 12px; align-items: center; gap: 20px; padding: 20px 2px; border: 0; border-bottom: 1px solid var(--health-line); border-radius: 0; background: transparent; color: var(--primary-text-color); text-align: left; }
  .metric-name { display: block; font-size: 16px; }
  .metric-source { display: block; margin-top: 5px; font-size: 12px; line-height: 1.5; color: var(--secondary-text-color); }
  .metric-value { text-align: right; font-variant-numeric: tabular-nums; }
  .metric-value .value { font-size: 23px; }
  .row-change { font-size: 12px; line-height: 1.5; }
  .row-arrow { font-size: 24px; color: var(--secondary-text-color); }
  .workout-strip { display: flex; gap: 28px; overflow-x: auto; padding: 4px 0 16px; }
  .workout-item { min-width: 180px; flex: 1; border-left: 2px solid var(--health-accent); padding-left: 16px; }
  .workout-item h3 { font-size: 17px; line-height: 1.4; margin: 12px 0 8px; overflow-wrap: anywhere; }
  .workout-item p { font-size: 14px; margin: 0 0 8px; }
  .source-status { border-top: 1px solid var(--health-line); padding: 22px 0; margin-top: 24px; }
  .source-status summary { cursor: pointer; padding: 8px 0; font-size: 15px; }
  .source-status summary span { color: var(--secondary-text-color); }
  .source-row { display: grid; grid-template-columns: 1fr 1fr 2fr; gap: 16px; padding: 14px 0; font-size: 13px; }
  a { color: var(--health-accent); }
  .intro-empty { max-width: 650px; padding: 40px 0; }
  .intro-empty h2 { font-size: 32px; color: var(--primary-text-color); line-height: 1.2; }
  .intro-empty p:not(.eyebrow), .empty-note { line-height: 1.6; color: var(--secondary-text-color); }
  dialog { box-sizing: border-box; width: min(720px, calc(100vw - 32px)); max-height: calc(100dvh - 40px); border: 1px solid var(--health-line); border-radius: 16px; padding: 28px; color: var(--primary-text-color); background: var(--card-background-color, var(--primary-background-color)); }
  dialog::backdrop { background: #0009; }
  .detail-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; position: sticky; top: -28px; padding: 16px 0; background: var(--card-background-color, var(--primary-background-color)); z-index: 2; }
  dialog .sub { text-align: left; font-size: 13px; }
  .detail-header h2 { margin: 8px 0 20px; color: var(--primary-text-color); font-size: 26px; }
  .detail-trend { margin: 0 0 24px; }
  .detail-trend .sparkline { max-height: 130px; }
  .reading-detail { border-top: 1px solid var(--health-line); padding-top: 24px; }
  .reading-value .value { font-size: 28px; }
  .notice { padding: 14px; border-left: 3px solid var(--health-accent); background: var(--secondary-background-color); line-height: 1.5; }
  .claim-row { display: flex; justify-content: space-between; gap: 16px; padding: 15px 0; border-bottom: 1px solid var(--health-line); }
  .source-id { display: block; font-size: 11px; overflow-wrap: anywhere; color: var(--secondary-text-color); margin-top: 5px; }
  button.record-button { width: 100%; border: 0; border-bottom: 1px solid var(--health-line); background: transparent; padding: 14px 8px; display: flex; justify-content: space-between; gap: 16px; text-align: left; border-radius: 0; }
  button.record-button.selected { background: var(--secondary-background-color); }
  .exclusion-control, .record-history { margin-top: 24px; }
  .excluded-toggle { display: flex; flex-direction: row; gap: 8px; align-items: center; font-size: 13px; }
  .excluded-toggle input { width: auto; }
  button:focus-visible, a:focus-visible, summary:focus-visible { outline: 2px solid var(--health-accent); outline-offset: 4px; }
  @media (max-width: 900px) { button.metric-row { grid-template-columns: 1fr 1fr 12px; gap: 14px; } .row-trend { grid-column: 1; grid-row: 2; max-width: 140px; } .row-change { grid-column: 2; grid-row: 2; } .row-arrow { grid-column: 3; grid-row: 1; } .lead-change { gap: 24px; } }
  @media (max-width: 600px) { .lead-change { grid-template-columns: 1fr; gap: 24px; padding: 24px 0; } .lead-chart { width: 100%; } .source-row { grid-template-columns: 1fr 1fr; } .source-row .sub { grid-column: 1 / -1; } dialog { padding: 20px; } .detail-header { top: -20px; } }
  @media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; } }
`;var je="M181 91L180 110Q148 108 135 130L119 184L109 232L87 311L83 330Q85 343 96 347L111 333L128 283L142 224L153 186L158 240L151 282Q147 309 156 338L163 413L167 489L166 542L155 577Q151 589 165 591L184 587L190 543L193 476L198 407L200 350L202 407L207 476L210 543L216 587L235 591Q249 589 245 577L234 542L233 489L237 413L244 338Q253 309 249 282L242 240L247 186L258 224L272 283L289 333L304 347Q315 343 317 330L313 311L291 232L281 184L265 130Q252 108 220 110L219 91Z",We=[{key:"shoulders",label:"Shoulders",sides:["front","back"],path:"M164 116Q145 116 137 138L129 168Q143 170 152 150Z"},{key:"chest",label:"Chest",sides:["front"],path:"M169 126Q158 137 157 156Q169 171 188 174Q196 176 196 166L196 139Q188 131 169 126Z"},{key:"biceps",label:"Biceps",sides:["front"],path:"M128 176Q136 172 143 176Q142 199 132 221Q126 232 120 236Q113 233 115 225Z"},{key:"triceps",label:"Triceps",sides:["back"],path:"M128 176Q136 172 143 176Q142 199 132 221Q126 232 120 236Q113 233 115 225Z"},{key:"forearms",label:"Forearms",sides:["front","back"],path:"M113 245Q119 241 125 240Q123 267 114 284L100 320Q95 323 92 317Z"},{key:"core",label:"Core",sides:["front"],path:"M160 175Q177 184 190 184L196 182L196 259Q183 270 167 275Q163 256 160 236Q157 203 160 175Z"},{key:"back",label:"Back",sides:["back"],path:"M167 122Q182 125 196 134L196 180Q184 190 169 193Q158 177 157 158ZM158 177L168 202Q184 198 196 191L196 248Q182 260 166 269Q159 250 158 231Z"},{key:"glutes",label:"Glutes",sides:["back"],path:"M165 280Q181 276 196 277L196 308Q193 321 184 326Q169 328 164 320Q154 309 165 280Z"},{key:"quads",label:"Quads",sides:["front"],path:"M163 295Q175 291 188 291Q194 316 193 337Q191 376 186 403Q180 414 171 413Q161 387 162 355Q155 325 163 295Z"},{key:"hamstrings",label:"Hamstrings",sides:["back"],path:"M164 338Q176 343 189 337Q192 365 186 410Q180 420 170 416Q163 397 163 370Z"},{key:"calves",label:"Calves",sides:["back"],path:"M171 429Q178 433 185 427Q190 454 183 490L177 537Q173 540 170 536L169 486Q163 455 171 429Z"}];function Y(t,e){(t.key==="Enter"||t.key===" ")&&(t.preventDefault(),e(t))}function xt(t){let e=t._body.regions;return a`<svg class="body-figure" viewBox="0 0 400 620" aria-label=${`Body, ${t._bodySide} view. Choose a muscle region to see recorded sets.`}>
    <ellipse cx="200" cy="59" rx="28" ry="36" class="body-outline" />
    <path d=${je} class="body-outline" />
    ${We.filter(s=>s.sides.includes(t._bodySide)).map(s=>{let i=e.find(n=>n.key===s.key),r=i?.heat||0;return b`<g class="body-region ${r?"recorded":""}" style=${`--region-heat: ${.18+r*.82}`} role="button" tabindex="0" aria-label=${`${s.label}, ${i?.recorded_sets||0} recorded sets`} @click=${n=>t._openRegion(s.key,n)} @keydown=${n=>Y(n,o=>t._openRegion(s.key,o))}>
        <title>${s.label}</title><path d=${s.path}/><path d=${s.path} transform="translate(400 0) scale(-1 1)"/>
      </g>`})}
    <g class="body-anchor" role="button" tabindex="0" aria-label="Body measurements: weight, body fat and lean mass" @click=${s=>t._openRegion("measurements",s)} @keydown=${s=>Y(s,i=>t._openRegion("measurements",i))}><circle cx="200" cy="226" r="15"/><path d="M194 226h12M200 220v12"/></g>
    <g class="body-dormant" role="button" tabindex="0" aria-label="Sleep, not available yet" @click=${s=>t._openRegion("sleep",s)} @keydown=${s=>Y(s,i=>t._openRegion("sleep",i))}><circle cx="200" cy="59" r="20"/><path d="M204 48a12 12 0 1 0 7 19a11 11 0 0 1 -7 -19Z"/></g>
    ${t._bodySide==="front"?b`<g class="body-dormant" role="button" tabindex="0" aria-label="Heart, not available yet" @click=${s=>t._openRegion("heart",s)} @keydown=${s=>Y(s,i=>t._openRegion("heart",i))}><circle cx="200" cy="148" r="17"/><path d="M200 157C182 146 188 134 196 142L200 146L204 142C212 134 218 146 200 157Z"/></g>`:l}
  </svg>`}function Fe(t){return t._overview.metrics.filter(e=>["weight","body_fat_percentage","lean_mass"].includes(e.metric)).map(e=>a`
    <button class="body-measurement ${e.stale?"stale":""}" @click=${s=>t._openDetail(e.metric,s)}>
      <span class="metric-name">${t._label(e.metric)}</span><span class="body-measurement-value">${e.current?t._metricValue(e.current):"No reading yet"}</span>
      <span class="metric-source">${e.current?`${t._providerName(e.current.provider)} \xB7 ${e.stale?"Older reading \xB7 ":""}${t._when(e.current.observed_at)}`:"Connect a source or log a reading"}</span>
      <span class="body-change">${H(t,e)}</span>
    </button>`)}function Ze(t){let e=t._body;return e?a`<section class="body-intro"><div><p class="eyebrow">Experimental</p><h2>Your recorded week</h2><p class="sub">${e.workout_count} completed ${e.workout_count===1?"workout":"workouts"} in the last seven days. Choose a region to see its sets.</p></div><button @click=${()=>{t._bodySide=t._bodySide==="front"?"back":"front"}}>Show ${t._bodySide==="front"?"back":"front"}</button></section>
    ${t._bodyError?a`<p class="error" role="alert">${t._bodyError}<button @click=${()=>t._loadBody()}>Try again</button></p>`:l}
    ${e.truncated||e.incomplete_workouts?a`<p class="notice">${e.truncated?`Showing the latest ${e.workouts.length} of ${e.workout_count} workouts. `:""}${e.incomplete_workouts?`${e.incomplete_workouts} ${e.incomplete_workouts===1?"workout has":"workouts have"} incomplete exercise detail.`:""} Colors reflect the usable records shown here.</p>`:l}
    <div class="body-layout"><div class="body-art"><p class="body-side" aria-live="polite">${t._bodySide}</p>${xt(t)}<div class="body-legend"><span>Fewer</span><span class="heat-scale" aria-hidden="true"></span><span>More</span></div><p class="body-legend-copy">Recent recorded sets, fading over seven days.<br/>Color is relative to your most active region.</p></div>
    <aside class="body-context"><section><p class="eyebrow">Body measurements</p><div class="body-measurements">${Fe(t)}</div></section>
      <section class="body-future"><p class="eyebrow">Still to come</p><button @click=${s=>t._openRegion("sleep",s)}><span class="future-symbol" aria-hidden="true">◔</span><span>Sleep<span class="metric-source">Not available yet</span></span></button><button @click=${s=>t._openRegion("heart",s)}><span class="future-symbol" aria-hidden="true">♡</span><span>Heart<span class="metric-source">Not available yet</span></span></button></section>
      ${e.workouts_without_sets?a`<p class="sub">${e.workouts_without_sets} ${e.workouts_without_sets===1?"workout has":"workouts have"} no usable non-warmup sets. Workout summaries remain available below.</p>`:l}
      ${e.unmapped_count?a`<details class="body-unmapped"><summary>${e.unmapped_count} unmapped exercise ${e.unmapped_count===1?"entry":"entries"}</summary><p class="sub">These names aren't in the exercise map yet. Their sets don't color the figure.</p><ul>${e.unmapped.map(s=>a`<li>${s.name}${s.occurrences>1?` (${s.occurrences})`:""}</li>`)}</ul><p class="sub">Up to 20 names shown. Open a workout below for its exercise detail.</p></details>`:l}
    </aside></div>
    <section class="body-workouts"><div class="section-heading"><h2>Recorded workouts</h2><span class="sub">Last seven days</span></div>${e.workouts.length?e.workouts.map(s=>Ke(t,s)):a`<p class="empty-note">No workouts recorded this week. A source with exercise and set detail will light up the figure as completed workouts arrive.</p>`}</section>`:t._bodyError?a`<p class="error" role="alert">${t._bodyError}<button @click=${()=>t._loadBody()}>Try again</button></p>`:a`<p role="status">Loading Body view…</p>`}function Ke(t,e){return a`<button class="record-button" @click=${s=>t._openWorkout(e.id,s)}><span>${e.title}<span class="metric-source">${t._providerName(e.provider)} · ${new Date(e.ended_at).toLocaleString()}</span></span><span>${e.recorded_sets} sets<span class="metric-source">${t._fmt(e.duration_seconds/60,0)} min</span></span></button>`}function wt(t,e){let s=[];if(e.reps!==void 0&&s.push(`${t._fmt(e.reps,0)} reps`),e.weight_kg!==void 0){let i=t._display(e.weight_kg,"kg");s.push(`${t._fmt(i.value)} ${i.unit}`)}if(e.duration_seconds!==void 0&&s.push(`${t._fmt(e.duration_seconds,0)} sec`),e.distance_m!==void 0){let i=t._display(e.distance_m,"m");s.push(`${t._fmt(i.value)} ${i.unit}`)}return s.join(" \xB7 ")}function Ye(t){if(!t._bodyRegion)return l;let e=t._bodyRegion,s=t._body,i=s?.regions.find(o=>o.key===e),r=i?.label||{measurements:"Body measurements",sleep:"Sleep",heart:"Heart",workout:"Workout"}[e],n;if(t._workoutId){let o=t._workoutDetail;r=o?.title||"Workout",n=a`${t._workoutLoading?a`<p role="status">Loading workout…</p>`:l}
      ${t._workoutError?a`<p class="error" role="alert">${t._workoutError}<button @click=${()=>t._loadWorkout(t._workoutId)}>Try again</button></p>`:l}
      ${o?a`<p>${t._providerName(o.provider)} · ${new Date(o.ended_at).toLocaleString()}</p><p class="sub">${t._fmt(o.duration_seconds/60,0)} min · ${o.workout_type}</p><p class="source-id">Source record: ${o.source}</p>
        ${o.incomplete?a`<p class="notice">Some exercise detail is incomplete or exceeds this view's limits. The original workout is kept in your history.</p>`:l}
        ${o.exercises.length?o.exercises.map(c=>a`<details class="exercise-detail"><summary>${c.name}<span>${c.recorded_sets} sets</span></summary><p class="sub">${c.regions.length?c.regions.map(d=>s.regions.find(h=>h.key===d)?.label||d).join(", "):"Unmapped exercise"}</p>${c.notes?a`<p class="exercise-notes">${c.notes}</p>`:l}<ol>${c.sets.map(d=>a`<li><span>${wt(t,d)}</span><span class="sub">${d.warmup?"Warmup, not counted":d.type}</span></li>`)}</ol></details>`):a`<p>No usable exercise detail was recorded for this workout.</p>`}`:l}`}else if(e==="measurements")n=a`<p class="sub">The same canonical readings and trends as Overview. Choose a metric to inspect its sources.</p>${Fe(t)}`;else if(e==="sleep"||e==="heart")n=a`<p>Not available yet.</p><p class="sub">This region is reserved for a future ${e==="sleep"?"sleep":"heart data"} view.</p>`;else{let o=s.workouts.filter(c=>c.regions.includes(e));n=a`<p class="region-count">${i?.recorded_sets||0}<span> recorded sets</span></p><p class="sub">Non-warmup sets from the last seven days. Color fades with time and is relative to the most active region.</p>${o.length?o.map(c=>Ke(t,c)):a`<p>No mapped sets for this region in the recorded week.</p>`}`}return K(t,r,"Training and sources",n)}var Ge=v`
  .body-intro { display: flex; justify-content: space-between; align-items: center; gap: 24px; border-top: 1px solid var(--health-line); padding-top: 28px; }
  .body-intro h2 { font-size: 28px; font-weight: 500; margin: 10px 0; color: var(--primary-text-color); }
  .body-intro .sub, .body-context .sub { font-size: 13px; line-height: 1.6; text-align: left; }
  .body-layout { display: grid; grid-template-columns: minmax(250px, 1fr) minmax(240px, .8fr); gap: 64px; }
  .body-art { text-align: center; }
  .body-side { font-size: 11px; text-transform: uppercase; letter-spacing: .12em; color: var(--secondary-text-color); margin: 22px 0 0; }
  .body-figure { display: block; height: 530px; max-width: 100%; margin: 0 auto; }
  .body-outline { fill: var(--secondary-background-color); stroke: var(--secondary-text-color); stroke-width: 1.2; }
  .body-region { cursor: pointer; outline: none; }
  .body-region path { fill: var(--secondary-text-color); fill-opacity: .15; stroke: var(--primary-background-color); stroke-width: 2; stroke-linejoin: round; transition: fill-opacity .2s; }
  .body-region.recorded path { fill: var(--health-accent); fill-opacity: var(--region-heat); }
  .body-region:hover path, .body-region:focus-visible path { stroke: var(--primary-text-color); stroke-width: 2.5; }
  .body-anchor { cursor: pointer; outline: none; }
  .body-anchor circle { fill: var(--primary-background-color); stroke: var(--secondary-text-color); }
  .body-anchor path { stroke: var(--primary-text-color); stroke-width: 1.5; }
  .body-anchor:hover circle, .body-anchor:focus-visible circle { stroke: var(--primary-text-color); stroke-width: 3; }
  .body-dormant { cursor: pointer; outline: none; fill: none; stroke: var(--secondary-text-color); opacity: .65; }
  .body-dormant circle { fill: var(--primary-background-color); stroke-dasharray: 2 3; }
  .body-dormant:hover, .body-dormant:focus-visible { opacity: 1; stroke: var(--primary-text-color); stroke-width: 2; }
  .body-legend { display: flex; align-items: center; justify-content: center; gap: 10px; font-size: 11px; color: var(--secondary-text-color); }
  .heat-scale { height: 6px; width: 120px; border-radius: 4px; background: linear-gradient(to right, color-mix(in srgb, var(--health-accent) 18%, transparent), var(--health-accent)); }
  .body-legend-copy { font-size: 12px; line-height: 1.6; color: var(--secondary-text-color); }
  .body-context { padding-top: 44px; min-width: 0; }
  button.body-measurement { display: grid; grid-template-columns: 1fr auto; gap: 4px 16px; text-align: left; width: 100%; padding: 20px 0; border: 0; border-bottom: 1px solid var(--health-line); border-radius: 0; background: transparent; color: var(--primary-text-color); }
  .body-measurement .metric-source, .body-change { grid-column: 1 / -1; }
  .body-measurement-value { font-size: 21px; font-variant-numeric: tabular-nums; }
  .body-change { font-size: 12px; color: var(--secondary-text-color); line-height: 1.5; }
  .body-future { margin-top: 36px; }
  .body-future button { display: flex; gap: 16px; align-items: center; width: 100%; margin-top: 16px; padding: 12px 0; border: 0; background: transparent; text-align: left; color: var(--secondary-text-color); }
  .future-symbol { display: grid; place-items: center; width: 38px; height: 38px; border: 1px dashed var(--health-line); border-radius: 50%; font-size: 23px; }
  .body-unmapped { margin-top: 24px; font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }
  .body-unmapped summary { cursor: pointer; }
  .body-workouts { margin-top: 40px; }
  .region-count { font-size: 44px; font-variant-numeric: tabular-nums; margin: 20px 0 8px; }
  .region-count span { font-size: 17px; }
  .exercise-detail { border-top: 1px solid var(--health-line); padding: 18px 0; }
  .exercise-detail summary { display: flex; justify-content: space-between; cursor: pointer; gap: 20px; font-size: 15px; }
  .exercise-detail summary span { white-space: nowrap; color: var(--secondary-text-color); font-size: 13px; }
  .exercise-detail ol { padding-left: 24px; }
  .exercise-detail li { padding: 7px 0; }
  .exercise-detail li .sub { display: block; font-size: 12px; }
  .exercise-notes { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; }
  @media (max-width: 800px) { .body-layout { gap: 28px; grid-template-columns: minmax(200px, 1fr) minmax(220px, 1fr); } .body-figure { height: 490px; } }
  @media (max-width: 560px) { .body-layout { display: block; } .body-context { padding-top: 24px; } .body-intro h2 { font-size: 23px; } .body-intro { gap: 12px; } .body-figure { height: 480px; } }
  @media (prefers-reduced-motion: reduce) { .body-region path { transition: none; } }
`;function x(t){return JSON.stringify(Object.fromEntries(Object.keys(t).sort().map(e=>[e,t[e]])))}function Je(t,e){try{let s=JSON.parse(t),i=e==="sleep"?["provider","source_id"]:["provider","source_id","metric","context","algorithm_id","algorithm_version"];return!s||Array.isArray(s)||Object.keys(s).length!==i.length||!i.every(r=>Object.hasOwn(s,r))||![s.provider,s.source_id].every(r=>typeof r=="string"&&r.length>0)||e==="recovery"&&(!["resting_heart_rate","hrv_sdnn","hrv_rmssd","respiratory_rate"].includes(s.metric)||!["spot","sleep_summary","daily_summary","unknown"].includes(s.context)||![s.algorithm_id,s.algorithm_version].every(r=>r===null||typeof r=="string"&&r.length>0))?void 0:s}catch{return}}function z(t,e){let s=new Intl.DateTimeFormat("en-US",{timeZone:e,year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date(t)),i=r=>s.find(n=>n.type===r).value;return`${i("year")}-${i("month")}-${i("day")}`}function Xe(t,e){let s=new Date(`${t}T12:00:00Z`);return s.setUTCDate(s.getUTCDate()+e),s.toISOString().slice(0,10)}function et(t,e){let s=Date.parse(`${t}T12:00:00Z`),i=s-48*36e5,r=s+48*36e5;for(;i<r;){let n=Math.floor((i+r)/2);z(n,e)<t?i=n+1:r=n}return new Date(i).toISOString()}function be(t){return t?.code==="unauthorized"?"You don't have permission to read this history.":"History could not refresh. Check the connection and try again."}var G=class{constructor(e){this.host=e,this.version=0,this.selectionVersion=0,this.detailVersion=0,this.listVersion=0,this.active=!0,this.domain=void 0,this.days=28,this.sources=[],this.records=[],this.loading=!1}update(){this.host.requestUpdate?.()}ws(e,s={}){return this.host.hass.callWS({type:`${this.host._domain}/${e}`,...s})}get timezone(){return this.host.hass?.config?.time_zone||"UTC"}get admin(){return!!this.host.hass?.user?.is_admin}get preference(){return`${this.host._domain}:${this.host.hass?.user?.id||"local"}:${this.domain}:source`}get descriptor(){return this.sources.find(e=>x(e.series_key)===x(this.selected||{}))}get ownsSelection(){return!!this.selected}invalidate(){this.version++,this.selectionVersion++,this.detailVersion++,this.listVersion++,this.detail=void 0,this.detailError=void 0,this.detailLoading=!1,this.listLoading=!1,this.listError=void 0,this.listNotice=void 0,this.listDay=void 0,this.recordCursor=void 0,this.sourceLoading=!1,this.stale=!1}disconnect(){this.active=!1,this.invalidate()}connect(){this.active=!0}navigate(e){if(this.invalidate(),!["sleep","recovery"].includes(e)){this.domain=void 0;return}if(this.domain!==e){this.domain=e,this.endDate=z(Date.now(),this.timezone),this.autoEnd=!0,this.selected=void 0,this.sources=[],this.records=[],this.series=void 0,this.lastSuccess=void 0,this.error=void 0,this.excluded=!1;try{this.selected=Je(window.localStorage.getItem(this.preference),e)}catch{}}}select(e){this.invalidate(),this.selected=Je(e,this.domain),this.series=void 0,this.records=[],this.lastSuccess=void 0,this.listDay=void 0;try{this.selected?window.localStorage.setItem(this.preference,x(this.selected)):window.localStorage.removeItem(this.preference)}catch{}return this.refresh()}setRange(e,s=this.endDate){return this.invalidate(),this.days=e,this.endDate=s,this.autoEnd=s===z(Date.now(),this.timezone),this.series=void 0,this.records=[],this.lastSuccess=void 0,this.listDay=void 0,this.refresh()}async refresh(e=this.domain){if(e!==this.domain&&this.navigate(e),!this.domain||!this.active)return;this.autoEnd&&(this.endDate=z(Date.now(),this.timezone));let s=++this.version;this.listVersion++;let i=()=>this.active&&s===this.version;this.loading=!0,this.error=void 0,this.update();try{let r=await this.ws("derived_sources",{domain:this.domain,limit:50});if(!i())return;if(this.sources=r.sources,this.sourceCursor=r.next_cursor,!this.selected&&!this.sourceCursor&&this.sources.length===1){this.selected=this.sources[0].series_key;try{window.localStorage.setItem(this.preference,x(this.selected))}catch{}}if(!this.selected){this.series=void 0,this.records=[];return}let n=await this.ws("derived_series",{domain:this.domain,series_key:this.selected,days:this.days,end_date:this.endDate,timezone:this.timezone});if(!i())return;this.series=n,this.lastSuccess=new Date().toISOString(),this.stale=!1,await this.loadRecords(!1,s),i()&&this.detail&&!this.detailLoading&&!this.mutation&&await this.openDetail(this.detail.id,void 0,!0,!1)}catch(r){i()&&(this.error=be(r),this.stale=!!this.series)}finally{i()&&(this.loading=!1,this.update())}}async moreSources(){if(!this.sourceCursor||this.sourceLoading)return;let e=this.version;this.sourceLoading=!0;try{let s=await this.ws("derived_sources",{domain:this.domain,limit:50,cursor:this.sourceCursor});if(e!==this.version||!this.active)return;this.sources=[...this.sources,...s.sources],this.sourceCursor=s.next_cursor}catch(s){if(e!==this.version||!this.active)return;s?.code==="stale_cursor"?await this.refresh():this.error=be(s)}finally{this.sourceLoading=!1,this.update()}}async loadRecords(e=!1,s=this.version,i=!0){if(!this.selected||!this.active)return;let r=++this.listVersion,n=()=>s===this.version&&r===this.listVersion&&this.active,o=this.listDay||Xe(this.endDate,1-this.days),c=Xe(this.listDay||this.endDate,1),d=et(o,this.timezone),h=et(c,this.timezone);this.listLoading=!0,this.listError=void 0,this.update();try{let u=d===h?{sessions:[],observations:[],next_cursor:null}:await this.ws(this.domain==="sleep"?"sleep_sessions":"recovery_observations",{start:d,end:h,excluded:!!this.excluded,limit:50,...this.domain==="sleep"?{source:this.selected,date_basis:this.listDay?"ended_at":"overlap"}:{series:this.selected},...e&&this.recordCursor?{cursor:this.recordCursor}:{}});if(!n())return;this.records=u.sessions||u.observations,this.recordCursor=u.next_cursor,this.listPage=e?(this.listPage||1)+1:1}catch(u){if(!n())return;u?.code==="stale_cursor"&&i?(this.listNotice="History changed. The list restarted at its first page.",await this.loadRecords(!1,s,!1)):this.listError=be(u)}finally{n()&&(this.listLoading=!1,this.update())}}drill(e){return this.listDay=e,this.excluded=!1,this.loadRecords()}showExcluded(e){return this.excluded=e,this.loadRecords()}closeDetail(){this.detailVersion++,this.detail=void 0,this.detailLoading=!1,this.detailError=void 0,this.detailNotice=void 0,this.update(),this.opener?.focus()}async openDetail(e,s,i=!0,r=!0){this.opener=s?.currentTarget||this.opener;let n=this.selectionVersion,o=++this.detailVersion,c=()=>this.active&&n===this.selectionVersion&&o===this.detailVersion;r&&(this.detail=void 0),this.detailId=e,this.detailError=void 0,this.detailNotice=void 0,this.detailLoading=!0,this.intervalPage=0,this.update();try{let d=this.domain==="sleep"?"sleep_session":"recovery_observation",h=this.domain==="sleep"?{session_id:e,limit:128}:{record_id:e},u=await this.ws(d,h);if(!c()||(this.detail={...u,stages:[],in_bed_intervals:[],completeTimeline:this.domain!=="sleep"},this.update(),await this.host.updateComplete,!c()))return;if(r&&this.host.shadowRoot?.querySelector(".sparse-detail h3")?.focus(),this.domain==="sleep"&&u.status!=="deleted"){for(let p of["stages","in_bed_intervals"]){let m=p==="stages"?u:await this.ws(d,{...h,kind:p}),y=0;for(;m;){if(!c())return;if(m.source_revision!==u.source_revision||m.payload_hash!==u.payload_hash||m.started_at!==u.started_at||m.ended_at!==u.ended_at)throw{code:"stale_cursor"};if(++y>32||this.detail[p].length+(m.intervals?.length||0)>4096)throw{code:"invalid_detail"};this.detail={...this.detail,[p]:[...this.detail[p],...m.intervals||[]]},this.update(),m=m.next_cursor?await this.ws(d,{...h,kind:p,cursor:m.next_cursor}):null}}if(!c())return;this.detail={...this.detail,completeTimeline:!0}}}catch(d){if(!c())return;this.detail=void 0,d?.code==="stale_cursor"&&i?(await this.openDetail(e,void 0,!1,r),n===this.selectionVersion&&this.detailId===e&&this.active&&(this.detailNotice="This record changed. Its detail was reloaded.",this.update())):this.detailError=d?.code==="unauthorized"?"You don't have permission to read this record.":"This record could not load. Refresh it and try again."}finally{c()&&(this.detailLoading=!1,this.update())}}async exclude(){let e=this.detail;if(!e||!this.admin||e.status==="deleted"||this.mutation)return;let s=this.detailVersion,i=this.domain,r=()=>this.active&&this.domain===i&&this.detailVersion===s;this.mutation=e.id,this.detailError=void 0,this.update();try{if(await this.ws(i==="sleep"?"sleep_session_exclusion":"recovery_observation_exclusion",{...i==="sleep"?{session_id:e.id}:{record_id:e.id},excluded:!e.locally_excluded,expected_source_revision:e.source_revision,expected_payload_hash:e.payload_hash}),!r())return;await this.refresh(),this.active&&this.detailVersion===s&&this.domain===i&&await this.openDetail(e.id)}catch(n){if(!r())return;if(n?.code==="revision_conflict"){let o=this.selectionVersion;await this.openDetail(e.id),this.active&&this.domain===i&&this.selectionVersion===o&&this.detailId===e.id&&(this.detailNotice="The record changed. Review the refreshed details before choosing the action again.")}else this.detailError=n?.code==="unauthorized"?"Only an administrator can change local exclusions.":"The exclusion could not be confirmed. Refresh before trying again."}finally{this.mutation=void 0,this.update()}}};var A={no_observation:"No observation",incomplete_sleep:"Sleep duration is unknown because coverage is incomplete.",insufficient_history:"Baseline needs 14 days of data.",no_current_value:"No observation for the selected date.",constant_baseline:"Constant history has no standardized difference.",calculation_unavailable:"This calculation is unavailable."};function _(t,e=""){return t==null?"No observation":e==="s"?`${(t/3600).toLocaleString(void 0,{maximumFractionDigits:2})} h`:`${t.toLocaleString(void 0,{maximumFractionDigits:3})}${e?` ${e}`:""}`}function w(t,e){return t?new Intl.DateTimeFormat(void 0,{timeZone:e,dateStyle:"medium",timeStyle:"medium"}).format(new Date(t)):"Unknown"}function Q(t,e,s){let i=t[`${e==="start"?"started":"ended"}_at`],r=t[`${e}_zone`];if(r)return`${w(i,r)} (${r})`;let n=t[`${e}_offset_seconds`];if(n!=null){let o=new Date(Date.parse(i)+n*1e3).toISOString(),c=Math.abs(n)/60,d=`UTC${n<0?"-":"+"}${String(Math.floor(c/60)).padStart(2,"0")}:${String(c%60).padStart(2,"0")}`;return`${w(o,"UTC")} (${d}, reported offset)`}return`${w(i,s)} (${s} display time; source timezone unknown)`}function J(t){let e=t.series?.points||[],s=e.filter(h=>h.value!==null).map(h=>h.value);if(!s.length)return a`<p>No values in this range. Missing days stay empty.</p>`;let i=Math.min(...s),r=Math.max(...s)-i||1,n=h=>10+h/Math.max(1,e.length-1)*580,o=h=>130-(h-i)/r*115,c=[],d="";for(let[h,u]of e.entries())u.value===null?(d&&c.push(d),d=""):d+=`${d?" L":"M"}${n(h)},${o(u.value)}`;return d&&c.push(d),a`<svg class="sparse-chart" viewBox="0 0 600 150" role="img" aria-label="Daily history. Gaps mean no known value. The table below contains each date and value.">
    ${c.map(h=>b`<path d=${h}></path>`)}
    ${e.map((h,u)=>h.value===null?l:b`<circle cx=${n(u)} cy=${o(h.value)} r="3"><title>${h.date}: ${_(h.value,h.unit)}; ${t.descriptor?.display_label||x(t.selected)}; ${h.started_at||h.observed_at||""} to ${h.ended_at||h.observed_at||""}; ${h.selection_rule}; ${h.value_basis}</title></circle>`)}
  </svg>`}function X(t,e){let s=t.selected?x(t.selected):"";return a`<div class="sparse-heading"><h2>${e}</h2><p>Display timezone: ${t.timezone}${t.host.hass?.config?.time_zone?"":" (Home Assistant timezone unavailable; using UTC)"}</p></div>
    <div class="sparse-controls">
      <label>Source and method<select aria-label="Source and method" .value=${s} @change=${i=>t.select(i.target.value)}>
        <option value="" ?selected=${!s}>Choose a source</option>
        ${s&&!t.descriptor?a`<option value=${s} selected>Saved selection: ${s}</option>`:l}
        ${t.sources.map(i=>a`<option value=${x(i.series_key)} ?selected=${s===x(i.series_key)}>${i.display_label}</option>`)}
      </select></label>
      <label>History<select aria-label="History range" .value=${String(t.days)} @change=${i=>t.setRange(Number(i.target.value))}>${[7,28,90].map(i=>a`<option value=${i} ?selected=${t.days===i}>${i} days</option>`)}</select></label>
      <label>End date<input type="date" aria-label="History end date" .value=${t.endDate||""} max=${z(Date.now(),t.timezone)} @change=${i=>i.target.value&&t.setRange(t.days,i.target.value)}></label>
    </div>
    ${t.sourceCursor?a`<button @click=${()=>t.moreSources()} ?disabled=${t.sourceLoading}>${t.sourceLoading?"Loading sources":"More sources"}</button>`:l}
    ${t.loading?a`<p role="status">Loading ${e.toLowerCase()} history.</p>`:l}
    ${t.error?a`<p class="sparse-notice" role="alert">${t.error} ${t.stale?"Displayed values are not current.":""}</p>`:l}
    ${t.lastSuccess?a`<p class="sparse-muted">Last successful refresh: ${w(t.lastSuccess,t.timezone)}</p>`:l}
    ${!t.loading&&!t.sources.length&&!t.selected&&!t.error?a`<p>No ${e.toLowerCase()} source yet. These views don't connect to your phone or create records. A compatible provider must supply this history first.</p>`:l}
    ${!t.selected&&t.sources.length?a`<p>Choose a source before viewing history. Accounts and methods are kept separate.</p>`:l}
    ${t.selected?a`<p class="sparse-source">${t.descriptor?.display_label||"Saved source selection"}<br>Capture: ${t.descriptor?.capture_state||"unknown"}. Retained history: ${t.descriptor?t.descriptor.retained_history_available?"available":"unavailable":t.sourceCursor?"not established on this source page":"unavailable"}.</p>`:l}`}function ee(t){return t.series?a`<div class="sparse-summary">${Object.entries(t.series.rolling).map(([e,s])=>a`<div><h3>${e}-day history</h3><p>${_(s.mean,t.series.points[0]?.unit)}</p><p>${s.n}/${s.possible_days} days present. Complete days only.</p><p>Trend: ${s.trend_slope===null?s.trend_reason==="calculation_unavailable"?A.calculation_unavailable:"Needs at least 3 days of data":_(s.trend_slope,`${t.series.points[0]?.unit}/day`)}</p>${s.mean_reason==="calculation_unavailable"||s.trend_reason==="calculation_unavailable"?a`<p>${A.calculation_unavailable}</p>`:l}</div>`)}</div>`:l}function te(t){return t.series?a`<details class="sparse-daily"><summary>Daily values and record choices</summary><div class="sparse-table"><table><caption>Daily history in ${t.timezone}</caption><thead><tr><th scope="col">Date</th><th scope="col">Value</th><th scope="col">Record choice</th><th scope="col">Inspect</th></tr></thead><tbody>${t.series.points.map(e=>a`<tr><td>${e.date}${e.complete_day?l:a`<br>Incomplete day`}</td><td>${e.value===null?A[e.null_reason]||A.no_observation:_(e.value,e.unit)}<br>${e.value_basis.replaceAll("_"," ")}</td><td>${e.selection_rule.replaceAll("_"," ")}${e.alternative_count?a`<br>${e.alternative_count} other record${e.alternative_count===1?"":"s"}`:l}</td><td><button @click=${()=>t.drill(e.date)} aria-label=${`List records ending on ${e.date}`}>List</button>${e.selected_record_id?a`<button @click=${s=>t.openDetail(e.selected_record_id,s)} aria-label=${`Inspect selected record on ${e.date}`}>Detail</button>`:l}</td></tr>`)}</tbody></table></div></details>`:l}function se(t){return t.selected?a`<section class="sparse-records" aria-label="Underlying source records"><h3>${t.listDay?`Records ending on ${t.listDay}`:"Underlying records in this range"}</h3>
    <p>${t.domain==="sleep"?t.listDay?"Wake-date list. Naps and overlapping sessions are separate records.":"Sessions overlapping this display range, including naps.":"Individual records. Daily charts select the latest record, not an average."}</p>
    <label class="sparse-check"><input type="checkbox" .checked=${!!t.excluded} @change=${e=>t.showExcluded(e.target.checked)}> Show locally excluded records</label>
    ${t.listDay?a`<button @click=${()=>{t.listDay=void 0,t.loadRecords()}}>Show whole range</button>`:l}
    ${t.listNotice?a`<p role="status">${t.listNotice}</p>`:l}
    ${t.listLoading?a`<p role="status">Loading records.</p>`:l}
    ${t.listError?a`<p role="alert">${t.listError} Previously listed records may be stale.</p>`:l}
    ${!t.listLoading&&!t.records.length?a`<p>${t.excluded?"No locally excluded records in this range.":t.descriptor?.excluded_count&&!t.descriptor.active_count?"This source has only excluded records. Choose Show locally excluded records to inspect them.":"No records in this range."}</p>`:l}
    <ul class="sparse-record-list">${t.records.map(e=>a`<li><div>${w(e.ended_at,t.timezone)}<br>${t.domain==="recovery"?`${_(e.value,e.unit)} \xB7 ${e.context?.replaceAll("_"," ")}`:`Asleep: ${e.asleep_duration_us===null?"Unknown":_(e.asleep_duration_us/1e6,"s")}`}<br>${e.status}</div><button @click=${s=>t.openDetail(e.id,s)} aria-label=${`Inspect record ending ${w(e.ended_at,t.timezone)}`}>Inspect</button></li>`)}</ul>
    <div class="sparse-controls">${t.listPage>1?a`<button @click=${()=>t.loadRecords()}>First page</button>`:l}${t.recordCursor?a`<button ?disabled=${t.listLoading} @click=${()=>t.loadRecords(!0)}>Next 50 records</button>`:l}</div>
  </section>`:l}function ie(t,e){if(!t.detail&&!t.detailLoading&&!t.detailError)return l;let s=t.detail;return a`<section class="sparse-detail" role="region" aria-label="Selected record detail"><div class="sparse-controls"><h3 tabindex="-1">Record detail</h3><button @click=${()=>t.closeDetail()}>Close detail</button></div>
    ${t.detailLoading?a`<p role="status">Loading detail${s&&!s.completeTimeline?"; timeline is partial":""}.</p>`:l}
    ${t.detailNotice?a`<p role="status">${t.detailNotice}</p>`:l}${t.detailError?a`<p role="alert">${t.detailError}</p><button @click=${()=>t.openDetail(t.detailId)}>Refresh detail</button>`:l}
    ${s?a`<p>Status: ${s.status}. Revision: ${s.source_revision}.</p><dl><dt>Start</dt><dd>${Q(s,"start",t.timezone)}</dd><dt>End</dt><dd>${Q(s,"end",t.timezone)}</dd></dl>${s.status==="deleted"?a`<p>This record was deleted upstream and cannot be restored here.</p>`:e}
      ${t.admin&&s.status!=="deleted"?a`<div class="sparse-exclusion"><p>Local exclusion hides this source record from summaries. It does not delete upstream data. Restore clears local exclusion only.</p><button ?disabled=${!!t.mutation||t.detailLoading} @click=${()=>t.exclude()}>${t.mutation?"Saving exclusion":s.locally_excluded?"Restore to summaries":"Exclude from summaries"}</button></div>`:l}`:l}
  </section>`}var tt=v`
  .sparse-view { min-width:0; overflow-wrap:anywhere; }
  .sparse-heading h2 { margin-bottom:6px; }
  .sparse-muted,.sparse-source,.sparse-heading p { color:var(--secondary-text-color); font-size:.9rem; }
  .sparse-controls { display:flex; flex-wrap:wrap; gap:12px; align-items:end; margin:12px 0; }
  .sparse-controls label { display:flex; flex-direction:column; gap:6px; min-width:0; flex:1 1 140px; }
  .sparse-controls label:first-child { flex:3 1 240px; }
  .sparse-controls select,.sparse-controls input { box-sizing:border-box; width:100%; min-width:0; padding:10px; color:var(--primary-text-color); background:var(--card-background-color); border:1px solid var(--divider-color); border-radius:8px; }
  .sparse-view button:focus-visible,.sparse-view input:focus-visible,.sparse-view select:focus-visible,.sparse-view summary:focus-visible { outline:3px solid var(--primary-color); outline-offset:3px; }
  .sparse-summary { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,200px),1fr)); gap:16px; margin:18px 0; }
  .sparse-summary > div { border-top:1px solid var(--divider-color); padding-top:12px; }
  .sparse-summary h3 { margin:0; font-size:1rem; }
  .sparse-summary p { margin:8px 0; }
  .sparse-notice { border-left:3px solid var(--primary-color); padding:10px; }
  .sparse-chart { display:block; width:100%; height:auto; max-height:180px; }
  .sparse-chart path { fill:none; stroke:var(--primary-color,#03a9f4); stroke-width:2; }
  .sparse-chart circle { fill:var(--primary-color,#03a9f4); }
  .sparse-table { overflow-x:auto; max-width:100%; margin:12px 0; }
  .sparse-view table { width:100%; border-collapse:collapse; font-size:.88rem; }
  .sparse-view th,.sparse-view td { text-align:left; padding:10px 6px; border-bottom:1px solid var(--divider-color); vertical-align:top; }
  .sparse-view caption { text-align:left; margin:10px 0; }
  .sparse-view summary { cursor:pointer; padding:12px 0; }
  .sparse-records,.sparse-detail { border-top:1px solid var(--divider-color); margin-top:22px; padding-top:16px; }
  .sparse-record-list { list-style:none; margin:12px 0; padding:0; }
  .sparse-record-list li { display:flex; justify-content:space-between; align-items:center; gap:12px; padding:12px 0; border-bottom:1px solid var(--divider-color); }
  .sparse-record-list li > div { min-width:0; }
  .sparse-check { display:inline-flex; gap:8px; align-items:center; margin:8px 0; }
  .sparse-view dl { display:grid; grid-template-columns:auto minmax(0,1fr); gap:10px; }
  .sparse-view dd { margin:0; }
  .sparse-exclusion { margin-top:16px; padding-top:8px; border-top:1px solid var(--divider-color); }
  .stage-timeline { width:100%; height:100px; display:block; }
  .stage-legend { display:flex; flex-wrap:wrap; gap:12px; font-size:.85rem; }
  .stage-legend span { border-left:5px solid var(--stage-color); padding-left:6px; }
  @media(prefers-reduced-motion:reduce) { .sparse-view * { animation:none!important; transition:none!important; scroll-behavior:auto!important; } }
`;var st={rem:"#9470cb",light:"#6495c5",deep:"#426c9e",asleep_unspecified:"#8195b4",awake:"#b78954",awake_in_bed:"#b4a270",out_of_bed:"#927d6b"};function kt(t){let e=Date.parse(t.started_at),s=Date.parse(t.ended_at)-e,i=new Map;if(!(s>0))return i;for(let[r,n]of[["stages",t.stages],["context",t.in_bed_intervals]])for(let o of n||[]){let c=r==="context"?"in_bed":o.stage;if(c==="unknown")continue;let d=(Date.parse(o.start)-e)/s*600,h=(Date.parse(o.end)-Date.parse(o.start))/s*600,u=r==="context"?58:12;i.set(c,(i.get(c)||"")+`M${d},${u}h${h}v24h${-h}z`)}return i}function St(t){let e=t.detail;if(!e||e.status==="deleted")return l;let s=t.intervalKind||"stages",i=e[s]||[],r=Math.min(t.intervalPage||0,Math.max(0,Math.ceil(i.length/128)-1)),n=i.slice(r*128,(r+1)*128);return a`<dl><dt>Elapsed session envelope</dt><dd>${_(e.elapsed_us/1e6,"s")}</dd><dt>Asleep duration</dt><dd>${e.asleep_duration_us===null?"Unknown":_(e.asleep_duration_us/1e6,"s")} (${e.value_basis.replaceAll("_"," ")})</dd><dt>Stage coverage</dt><dd>${_(e.stage_coverage_us/1e6,"s")}</dd><dt>Unknown stage time</dt><dd>${_(e.unknown_stage_us/1e6,"s")}</dd><dt>Uncovered time</dt><dd>${_(e.uncovered_us/1e6,"s")}</dd></dl>
    ${e.summary_interval_disagreement?a`<p role="status">Reported totals and stage-derived totals disagree. Both are shown below.</p>`:l}
    ${e.context_disagreement?a`<p role="status">The reported in-bed context overlaps an out-of-bed stage. These source records are shown separately.</p>`:l}
    <div class="sparse-table"><table><caption>Source totals and interval totals, kept separate</caption><thead><tr><th scope="col">Type</th><th scope="col">Reported</th><th scope="col">Known intervals</th></tr></thead><tbody>${Object.entries(e.reported_totals||{}).map(([o,c])=>a`<tr><th scope="row">${o.replaceAll("_"," ")}</th><td>${c===null?"Not reported":_(c/1e6,"s")}</td><td>${e.interval_totals[o]===void 0?"Not available":_(e.interval_totals[o]/1e6,"s")}</td></tr>`)}</tbody></table></div>
    <h4>Stages and in-bed context</h4><p>Stages are the upper lane. In-bed context is the lower lane. Gaps are unknown or uncovered, not awake or asleep.</p>
    ${e.completeTimeline?a`<svg class="stage-timeline" viewBox="0 0 600 100" role="img" aria-label="Complete source interval timeline. Stage and in-bed lanes are separate; the interval table provides a text alternative.">${[...kt(e)].map(([o,c])=>b`<path d=${c} fill=${st[o]||"#8a9299"}><title>${o.replaceAll("_"," ")}</title></path>`)}</svg><p>All interval pages loaded.</p>`:a`<p role="status">Partial detail: loading interval pages before showing the complete timeline.</p>`}
    <div class="stage-legend">${Object.entries({...st,in_bed:"#8a9299"}).map(([o,c])=>a`<span style=${`--stage-color:${c}`}>${o.replaceAll("_"," ")}</span>`)}</div>
    <div class="sparse-controls"><label>Interval lane<select .value=${s} @change=${o=>{t.intervalKind=o.target.value,t.intervalPage=0,t.update()}}><option value="stages" ?selected=${s==="stages"}>Stages</option><option value="in_bed_intervals" ?selected=${s==="in_bed_intervals"}>In-bed context</option></select></label></div>
    <div class="sparse-table"><table><caption>${s==="stages"?"Stage":"In-bed"} intervals in ${t.timezone} display time. ${i.length?`${r*128+1} to ${r*128+n.length} of ${i.length} loaded intervals`:"No intervals reported"}.</caption><thead><tr><th scope="col">Type</th><th scope="col">Start</th><th scope="col">End</th></tr></thead><tbody>${n.map(o=>a`<tr><td>${(o.stage||"in_bed").replaceAll("_"," ")}</td><td>${w(o.start,t.timezone)}<br><small>${o.start}</small></td><td>${w(o.end,t.timezone)}<br><small>${o.end}</small></td></tr>`)}</tbody></table></div>
    <div class="sparse-controls"><button ?disabled=${r===0} @click=${()=>{t.intervalPage=r-1,t.update()}}>Previous intervals</button><button ?disabled=${(r+1)*128>=i.length} @click=${()=>{t.intervalPage=r+1,t.update()}}>Next intervals</button></div>`}function it(t){return a`<section class="card sparse-view" aria-label="Sleep history">${X(t,"Sleep")}
    ${t.selected?a`<p>Longest-session sleep duration by wake date. This isn't total daily sleep. Naps and overlapping sessions remain separate in the list.</p>${J(t)}${ee(t)}${te(t)}${se(t)}${ie(t,St(t))}`:l}
  </section>`}function At(t){let e=t.detail;return!e||e.status==="deleted"?l:a`<dl><dt>Value</dt><dd>${_(e.value,e.unit)}</dd><dt>Metric</dt><dd>${e.metric.replaceAll("_"," ")}</dd><dt>Context</dt><dd>${e.context.replaceAll("_"," ")}</dd><dt>Algorithm</dt><dd>${e.algorithm_id||"Unknown"}</dd><dt>Algorithm version</dt><dd>${e.algorithm_version||"Unknown"}</dd></dl>`}function Et(t){let e=t.series?.baseline;if(!e)return l;let s=t.series.points.at(-1);return a`<section aria-label="Personal baseline"><h3>Prior 28-day history</h3><p>${e.start_date} through ${e.end_date} (end date excluded). ${e.n}/${e.possible_days} days present (${Math.round(e.coverage*100)}% coverage).</p>
    ${e.mean===null?a`<p>${A[e.baseline_reason]||"Baseline unavailable."}</p>`:a`<p>Prior 28-day average: ${_(e.mean,s.unit)}</p>${e.deviation===null?a`<p>${A.no_current_value}</p>`:a`<p>Difference from average: ${_(e.deviation,s.unit)}</p>`}`}
    <details><summary>Technical detail: standardized difference</summary><p>${e.z===null?A[e.z_reason]||"Standardized difference unavailable.":_(e.z)}</p><p>Sample standard deviation: ${e.stddev===null?"Unavailable":_(e.stddev,s.unit)}. These values describe your own history. They aren't a readiness score or a clinical assessment.</p></details>
  </section>`}function rt(t){let e=t.series?.points.at(-1);return a`<section class="card sparse-view" aria-label="Recovery history">${X(t,"Recovery")}
    ${t.selected?a`<p>Metric: ${t.selected.metric.replaceAll("_"," ")}. Context: ${t.selected.context.replaceAll("_"," ")}. Algorithm: ${t.selected.algorithm_id||"unknown"}, version ${t.selected.algorithm_version||"unknown"}.</p>
      ${e?a`<h3>${e.date}: ${_(e.value,e.unit)}</h3>${e.complete_day?l:a`<p>Incomplete day. Historical rolling summaries exclude this date.</p>`}${e.alternative_count?a`<p>Latest record selected from ${e.alternative_count+1} same-day records. This is not a daily average.</p>`:l}${e.selected_record_id?a`<p>Selected window: ${Q(e,"start",t.timezone)} to ${Q(e,"end",t.timezone)}.</p>`:l}`:l}
      ${J(t)}${ee(t)}${Et(t)}${te(t)}${se(t)}${ie(t,At(t))}`:l}
  </section>`}var Lt=2.204622621848776,Dt=1/1609.344,re=[{key:"weight",label:"Weight"},{key:"body_fat_percentage",label:"Body fat"},{key:"lean_mass",label:"Lean mass"},{key:"steps",label:"Steps"},{key:"distance",label:"Distance"},{key:"active_energy",label:"Active energy"}],Rt=[7,30,90],ve={ha_entity:"Home Assistant sensors",manual:"Manual entries",withings:"Withings",fitbit:"Fitbit",hevy:"Hevy"},$e=class extends S{static properties={hass:{attribute:!1},narrow:{type:Boolean},panel:{attribute:!1},_overview:{state:!0},_body:{state:!0},_bodyError:{state:!0},_bodySide:{state:!0},_bodyRegion:{state:!0},_workoutId:{state:!0},_workoutDetail:{state:!0},_workoutLoading:{state:!0},_workoutError:{state:!0},_loading:{state:!0},_detailMetric:{state:!0},_detail:{state:!0},_records:{state:!0},_showExcluded:{state:!0},_detailError:{state:!0},_detailLoading:{state:!0},_busyId:{state:!0},_series:{state:!0},_tab:{state:!0},_metric:{state:!0},_days:{state:!0},_error:{state:!0},_form:{state:!0},_saving:{state:!0}};constructor(){super(),this._tab="overview",this._metric="weight",this._days=30,this._form=null,this._saving=!1,this._loadedOnce=!1,this._showExcluded=!1,this._records=[],this._request=0,this._detailRequest=0,this._dialogSession=0,this._bodySide="front",this._bodyRequest=0,this._workoutRequest=0,this._sparse=new G(this)}get _domain(){return this.panel&&this.panel.config&&this.panel.config.domain||"health_assistant"}get _imperial(){return!!(this.hass&&this.hass.config&&this.hass.config.unit_system&&this.hass.config.unit_system.length==="mi")}updated(e){if(e.has("hass")&&this.hass&&!this._loadedOnce){this._loadedOnce=!0;try{let s=window.localStorage.getItem(this._viewPreferenceKey);["overview","body","trends","sleep","recovery"].includes(s)&&(this._tab=s)}catch{}this._refresh()}}connectedCallback(){super.connectedCallback(),this._sparse.connect(),this.hass&&this._loadedOnce&&this._refresh(),this._timer=window.setInterval(()=>{this.hass&&!this._loading&&this._refresh()},6e4)}disconnectedCallback(){super.disconnectedCallback(),window.clearInterval(this._timer),this._request++,this._sparse.disconnect()}async _refresh(){let e=++this._request;this._loading=!0,this._error=void 0;try{if(["sleep","recovery"].includes(this._tab)){await this._sparse.refresh(this._tab);return}let s=await this.hass.callWS({type:`${this._domain}/overview`});e===this._request&&(this._overview=s),this._tab==="trends"&&await this._loadSeries(),this._tab==="body"&&await this._loadBody()}catch{e===this._request&&(this._error="Health data could not refresh. Check the integration and try again.")}finally{e===this._request&&(this._loading=!1)}}_providerName(e){return ve[e]||this._overview?.providers.find(s=>s.key===e)?.name||e.replaceAll("_"," ")}_label(e){return re.find(s=>s.key===e)?.label||e}async _openDetail(e,s){let i=++this._dialogSession;if(this._detailRequest++,this._workoutRequest++,this.shadowRoot.querySelector("dialog")?.open||(this._opener=s?.currentTarget),this._bodyRegion=void 0,this._detailMetric=e,this._detail=void 0,this._showExcluded=!1,this._records=[],await this.updateComplete,i!==this._dialogSession)return;let r=this.shadowRoot.querySelector("dialog");r.open||r.showModal(),await this._loadDetail()}_closeDetail(){this._dialogSession++,this._detailRequest++,this._workoutRequest++,this.shadowRoot.querySelector("dialog")?.close(),this._detailMetric=void 0,this._bodyRegion=void 0,this._workoutId=void 0,this._opener?.focus()}async _loadDetail(e,s=!1){let i=++this._detailRequest,r=this._detailMetric;if(!r)return;this._detailLoading=!0,this._detailError=void 0;let n=this._overview?.metrics.find(o=>o.metric===r)?.current;try{let o=await this.hass.callWS({type:`${this._domain}/observations`,metric:r,excluded:this._showExcluded,limit:20,...s&&this._nextRecord?{before_id:this._nextRecord}:{}}),c=e||(this._showExcluded?o.observations[0]?.id:n?.id),d=c?await this.hass.callWS({type:`${this._domain}/observation_detail`,observation_id:c}):void 0;if(i!==this._detailRequest)return;this._records=s?[...this._records,...o.observations]:o.observations,this._nextRecord=o.next_before_id,this._detail=d}catch{i===this._detailRequest&&(this._detailError="That reading could not load. It may have changed during a sync. Try again.")}finally{i===this._detailRequest&&(this._detailLoading=!1)}}async _toggleExclusion(){let e=this._detail?.observation;if(!e||this._busyId)return;let s=this._dialogSession,i=this._detailRequest,r=()=>s===this._dialogSession&&i===this._detailRequest;this._busyId=e.id,this._detailError=void 0;try{await this.hass.callWS({type:`${this._domain}/observation_exclusion`,observation_id:e.id,excluded:!e.excluded}),await this._refresh(),r()&&(i++,await this._loadDetail(e.id))}catch{r()&&(this._detailError="The reading could not be changed. Refresh and try again.")}finally{this._busyId=void 0,await this.updateComplete,r()&&this.shadowRoot.querySelector(".exclusion-control button")?.focus()}}async _loadSeries(){let e=(this._seriesRequest||0)+1;this._seriesRequest=e,this._series=void 0;try{let s=await this.hass.callWS({type:`${this._domain}/time_series`,metric:this._metric,days:this._days});e===this._seriesRequest&&(this._series=s)}catch{e===this._seriesRequest&&(this._error="Trend data could not load. Try refreshing.")}}get _viewPreferenceKey(){return`${this._domain}:${this.hass?.user?.id||"local"}:view`}async _loadBody(){let e=++this._bodyRequest;this._bodyError=void 0;try{let s=await this.hass.callWS({type:`${this._domain}/body`});e===this._bodyRequest&&(this._body=s)}catch{e===this._bodyRequest&&(this._bodyError="Body data could not refresh. Try again.")}}async _openRegion(e,s){let i=++this._dialogSession;if(this._detailRequest++,this._workoutRequest++,this.shadowRoot.querySelector("dialog")?.open||(this._opener=s?.currentTarget),this._detailMetric=void 0,this._bodyRegion=e,this._workoutId=void 0,this._workoutDetail=void 0,this._workoutError=void 0,await this.updateComplete,i!==this._dialogSession)return;let r=this.shadowRoot.querySelector("dialog");return r.open||r.showModal(),i}async _openWorkout(e,s){await this._openRegion("workout",s)===this._dialogSession&&await this._loadWorkout(e)}async _loadWorkout(e){let s=++this._workoutRequest,i=this._dialogSession;this._workoutId=e,this._workoutDetail=void 0,this._workoutLoading=!0,this._workoutError=void 0;try{let r=await this.hass.callWS({type:`${this._domain}/workout_detail`,workout_id:e});s===this._workoutRequest&&i===this._dialogSession&&(this._workoutDetail=r)}catch{s===this._workoutRequest&&i===this._dialogSession&&(this._workoutError="That workout could not load. Try again.")}finally{s===this._workoutRequest&&i===this._dialogSession&&(this._workoutLoading=!1)}}_setTab(e){this._sparse.navigate(e),this._tab=e;try{window.localStorage.setItem(this._viewPreferenceKey,e)}catch{}e==="trends"?this._loadSeries():this._refresh()}_setMetric(e){this._metric=e,this._loadSeries()}_setDays(e){this._days=e,this._loadSeries()}_display(e,s){return e==null?null:s==="kg"&&this._imperial?{value:e*Lt,unit:"lb"}:s==="m"&&this._imperial?{value:e*Dt,unit:"mi"}:s==="m"&&e>=1e3?{value:e/1e3,unit:"km"}:{value:e,unit:s}}_fmt(e,s=1){return new Intl.NumberFormat(void 0,{maximumFractionDigits:s}).format(e)}_when(e){let s=new Date(e),r=Math.floor((new Date-s)/864e5);return r<=0?s.toLocaleTimeString(void 0,{hour:"numeric",minute:"2-digit"}):r===1?"yesterday":r<7?`${r} days ago`:s.toLocaleDateString()}_metricValue(e,s=1){if(!e)return a`<span class="empty-value">no data</span>`;let i=this._display(e.value,e.unit),r=i.unit==="count"?l:a`<span class="unit">${i.unit}</span>`;return a`<span class="value">${this._fmt(i.value,s)}</span>${r}`}_defaultUnit(e){return e==="weight"||e==="lean_mass"?this._imperial?"lb":"kg":e==="distance"?this._imperial?"mi":"km":e==="body_fat_percentage"?"%":e==="active_energy"?"kcal":""}_localNow(e=0){let s=new Date(Date.now()-e*6e4),i=r=>String(r).padStart(2,"0");return`${s.getFullYear()}-${i(s.getMonth()+1)}-${i(s.getDate())}T${i(s.getHours())}:${i(s.getMinutes())}`}_openForm(e){this._error=void 0,this._form=this._form===e?null:e}_formValue(e){let s=this.shadowRoot.getElementById(e);return s?s.value.trim():""}async _submitMeasurement(e){e.preventDefault();let s=Number(this._formValue("m-value"));if(!Number.isFinite(s)){this._error="Enter a numeric value";return}let r={metric:this._formValue("m-metric"),value:s},n=this._formValue("m-unit");n&&n!=="count"&&(r.unit=n);let o=this._formValue("m-when");o&&(r.observed_at=new Date(o).toISOString()),await this._callAction("add_observation",r)}async _submitWorkout(e){e.preventDefault();let s=this._formValue("w-type"),i=this._formValue("w-start"),r=this._formValue("w-end");if(!s||!i||!r){this._error="Workout type, start, and end are required";return}let n={workout_type:s,start:new Date(i).toISOString(),end:new Date(r).toISOString()},o=this._formValue("w-title");o&&(n.title=o);let c=this._formValue("w-energy");c&&(n.energy_kcal=Number(c));let d=this._formValue("w-distance");d&&(n.distance=Number(d),n.distance_unit=this._imperial?"mi":"km"),await this._callAction("add_workout",n)}async _callAction(e,s){this._saving=!0,this._error=void 0;try{await this.hass.callService(this._domain,e,s),this._form=null,await this._refresh()}catch(i){this._error=i&&i.message||"Unable to save"}finally{this._saving=!1}}_measurementForm(){return this._form!=="measure"?l:a`
      <form class="entry" @submit=${this._submitMeasurement}>
        <label>Metric
          <select id="m-metric" @change=${e=>{let s=this.shadowRoot.getElementById("m-unit");s&&(s.value=this._defaultUnit(e.target.value))}}>
            ${re.map(e=>a`<option value=${e.key}>${e.label}</option>`)}
          </select>
        </label>
        <label>Value
          <input id="m-value" type="number" step="any" required />
        </label>
        <label>Unit
          <input id="m-unit" type="text" .value=${this._defaultUnit("weight")} />
        </label>
        <label>When
          <input id="m-when" type="datetime-local" .value=${this._localNow()} />
        </label>
        <button type="submit" class="primary" ?disabled=${this._saving}>
          ${this._saving?"Saving":"Save"}
        </button>
      </form>
    `}_workoutForm(){return this._form!=="workout"?l:a`
      <form class="entry" @submit=${this._submitWorkout}>
        <label>Type
          <input id="w-type" type="text" placeholder="running, strength, yoga" required />
        </label>
        <label>Title
          <input id="w-title" type="text" placeholder="optional" />
        </label>
        <label>Start
          <input id="w-start" type="datetime-local" .value=${this._localNow(60)} required />
        </label>
        <label>End
          <input id="w-end" type="datetime-local" .value=${this._localNow()} required />
        </label>
        <label>Energy (kcal)
          <input id="w-energy" type="number" step="any" placeholder="optional" />
        </label>
        <label>Distance (${this._imperial?"mi":"km"})
          <input id="w-distance" type="number" step="any" placeholder="optional" />
        </label>
        <button type="submit" class="primary" ?disabled=${this._saving}>
          ${this._saving?"Saving":"Save"}
        </button>
      </form>
    `}_renderOverview(){return He(this)}_chart(){let e=this._series;if(!e)return a`<p role="status">Loading trend…</p>`;if(e.points.length===0)return a`<p class="empty-value">
        No ${this._metricLabel().toLowerCase()} data in the last ${this._days} days.
      </p>`;let s=640,i=260,r={left:54,right:16,top:16,bottom:34},n=e.points.map(g=>({time:new Date(g.t).getTime(),shown:this._display(g.v,e.unit),provider:g.provider})),o=n[0].shown.unit,c=n.map(g=>g.shown.value),d=n.map(g=>g.time),h=Math.min(...c),u=Math.max(...c),p=u-h||Math.abs(u)*.1||1,m=Math.min(...d),y=Math.max(...d),f=y-m||1,E=g=>r.left+(g-m)/f*(s-r.left-r.right),V=g=>i-r.bottom-(g-(h-p*.05))/(p*1.1)*(i-r.top-r.bottom),ot=n.map((g,lt)=>`${lt===0?"M":"L"}${E(g.time).toFixed(1)},${V(g.shown.value).toFixed(1)}`).join(" "),at=n.length<=120?n.map(g=>b`<circle cx="${E(g.time)}" cy="${V(g.shown.value)}" r="3">
                <title>${this._fmt(g.shown.value)} ${o} · ${new Date(g.time).toLocaleString()} · ${ve[g.provider]||g.provider}</title>
              </circle>`):l,nt=[...new Set(e.points.map(g=>g.provider))].map(g=>ve[g]||g);return a`
      <svg viewBox="0 0 ${s} ${i}" role="img">
        <line class="axis" x1="${r.left}" y1="${i-r.bottom}" x2="${s-r.right}" y2="${i-r.bottom}"></line>
        <line class="axis" x1="${r.left}" y1="${r.top}" x2="${r.left}" y2="${i-r.bottom}"></line>
        <text class="tick" x="${r.left-8}" y="${V(u)+4}" text-anchor="end">${this._fmt(u)}</text>
        <text class="tick" x="${r.left-8}" y="${V(h)+4}" text-anchor="end">${this._fmt(h)}</text>
        <text class="tick" x="${r.left}" y="${i-10}">${new Date(m).toLocaleDateString()}</text>
        <text class="tick" x="${s-r.right}" y="${i-10}" text-anchor="end">${new Date(y).toLocaleDateString()}</text>
        <path class="line" d="${ot}"></path>
        ${at}
      </svg>
      <div class="sub caption">
        ${e.points.length} points${o==="count"?"":` (${o})`}
        ${e.downsampled?" \xB7 downsampled":""} · from ${nt.join(", ")}
      </div>
    `}_metricLabel(){let e=re.find(s=>s.key===this._metric);return e?e.label:this._metric}_renderTrends(){return a`
      <div class="card wide">
        <div class="selector">
          ${re.map(e=>a`<button
              class=${this._metric===e.key?"active":""}
              @click=${()=>this._setMetric(e.key)}
            >
              ${e.label}
            </button>`)}
        </div>
        <div class="selector">
          ${Rt.map(e=>a`<button
              class=${this._days===e?"active":""}
              @click=${()=>this._setDays(e)}
            >
              ${e} days
            </button>`)}
        </div>
        ${this._chart()}
      </div>
    `}render(){return a`
      <div class="wrapper">
        <header>
          <div class="header-identity">${this.narrow?a`<button aria-label="Open sidebar" @click=${()=>this.dispatchEvent(new window.Event("hass-toggle-menu",{bubbles:!0,composed:!0}))}>Menu</button>`:l}<div><h1>Health</h1><p class="page-subtitle">Your record, at a glance</p></div></div>
          <nav aria-label="Health views">
            <button @click=${this._refresh} ?disabled=${this._loading}>${this._loading?"Refreshing":"Refresh"}</button>
            <button
              class=${this._tab==="overview"?"active":""}
              aria-pressed=${this._tab==="overview"}
              @click=${()=>this._setTab("overview")}
            >
              Overview
            </button>
            <button
              class=${this._tab==="body"?"active":""}
              aria-pressed=${this._tab==="body"}
              @click=${()=>this._setTab("body")}
            >
              Body (experimental)
            </button>
            <button
              class=${this._tab==="trends"?"active":""}
              aria-pressed=${this._tab==="trends"}
              @click=${()=>this._setTab("trends")}
            >
              Trends
            </button>
            ${["sleep","recovery"].map(e=>a`<button class=${this._tab===e?"active":""} aria-pressed=${this._tab===e} @click=${()=>this._setTab(e)}>${e==="sleep"?"Sleep":"Recovery"}</button>`)}
          </nav>
        </header>
        ${this._error?a`<div class="card error">${this._error}</div>`:l}
        ${this._tab==="overview"?this._renderOverview():this._tab==="body"?Ze(this):this._tab==="sleep"?it(this._sparse):this._tab==="recovery"?rt(this._sparse):this._renderTrends()}
        ${this._bodyRegion?Ye(this):Qe(this)}
      </div>
    `}static styles=[Ve,Ge,tt,v`
    :host {
      display: block;
      height: 100%;
      overflow-y: auto;
      background: var(--primary-background-color);
      color: var(--primary-text-color);
      font-family: var(--paper-font-body1_-_font-family, sans-serif);
    }
    .wrapper {
      max-width: 1100px;
      margin: 0 auto;
      padding: 16px;
      box-sizing: border-box;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 16px;
    }
    h1 {
      font-size: 1.6em;
      font-weight: 400;
      margin: 0;
    }
    nav,
    .selector {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .selector {
      margin-bottom: 12px;
    }
    button {
      background: var(--card-background-color, #fff);
      color: var(--primary-text-color);
      border: 1px solid var(--divider-color, #444);
      border-radius: 16px;
      padding: 6px 14px;
      cursor: pointer;
      font: inherit;
    }
    button.active,
    button.primary {
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
      border-color: var(--primary-color);
    }
    button.ghost {
      margin-top: 14px;
      border-style: dashed;
    }
    button[disabled] {
      opacity: 0.6;
      cursor: default;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
    }
    .card {
      background: var(--card-background-color, #fff);
      border-radius: 12px;
      box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0, 0, 0, 0.2));
      padding: 16px 20px;
    }
    .card.wide {
      width: 100%;
      box-sizing: border-box;
    }
    .card.error {
      border-left: 4px solid var(--error-color, #b71c1c);
      margin-bottom: 16px;
    }
    .card.guide p {
      line-height: 1.5;
    }
    h2 {
      font-size: 1.05em;
      font-weight: 500;
      margin: 0 0 12px;
      color: var(--secondary-text-color);
    }
    .row {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-top: 10px;
    }
    .label {
      color: var(--secondary-text-color);
    }
    .value {
      font-size: 1.4em;
      font-weight: 500;
    }
    .unit {
      color: var(--secondary-text-color);
      font-size: 0.9em;
      margin-left: 2px;
    }
    .sub {
      color: var(--secondary-text-color);
      font-size: 0.78em;
      margin-top: 2px;
      text-align: right;
    }
    .sub.caption {
      text-align: left;
    }
    .empty-value {
      color: var(--secondary-text-color);
    }
    .entry {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 10px;
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid var(--divider-color, #444);
    }
    .entry label {
      display: flex;
      flex-direction: column;
      gap: 4px;
      font-size: 0.8em;
      color: var(--secondary-text-color);
    }
    .entry input,
    .entry select {
      background: var(--primary-background-color);
      color: var(--primary-text-color);
      border: 1px solid var(--divider-color, #444);
      border-radius: 8px;
      padding: 7px 9px;
      font: inherit;
      min-width: 0;
    }
    .entry button {
      align-self: end;
    }
    svg {
      width: 100%;
      height: auto;
      margin-top: 8px;
    }
    .axis {
      stroke: var(--divider-color, #666);
      stroke-width: 1;
    }
    .tick {
      fill: var(--secondary-text-color);
      font-size: 11px;
    }
    .line {
      fill: none;
      stroke: var(--primary-color, #03a9f4);
      stroke-width: 2;
    }
    circle {
      fill: var(--primary-color, #03a9f4);
    }
  `]};customElements.get("health-assistant-panel")||customElements.define("health-assistant-panel",$e);
/*! Bundled license information:

@lit/reactive-element/css-tag.js:
  (**
   * @license
   * Copyright 2019 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/reactive-element.js:
lit-html/lit-html.js:
lit-element/lit-element.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/is-server.js:
  (**
   * @license
   * Copyright 2022 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)
*/
