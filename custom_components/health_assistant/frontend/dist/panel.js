var Q=globalThis,U=Q.ShadowRoot&&(Q.ShadyCSS===void 0||Q.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,j=Symbol(),le=new WeakMap,C=class{constructor(e,t,i){if(this._$cssResult$=!0,i!==j)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,t=this.t;if(U&&e===void 0){let i=t!==void 0&&t.length===1;i&&(e=le.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&le.set(t,e))}return e}toString(){return this.cssText}},de=s=>new C(typeof s=="string"?s:s+"",void 0,j),w=(s,...e)=>{let t=s.length===1?s[0]:e.reduce((i,o,a)=>i+(r=>{if(r._$cssResult$===!0)return r.cssText;if(typeof r=="number")return r;throw Error("Value passed to 'css' function must be a 'css' function result: "+r+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(o)+s[a+1],s[0]);return new C(t,s,j)},ce=(s,e)=>{if(U)s.adoptedStyleSheets=e.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(let t of e){let i=document.createElement("style"),o=Q.litNonce;o!==void 0&&i.setAttribute("nonce",o),i.textContent=t.cssText,s.appendChild(i)}},F=U?s=>s:s=>s instanceof CSSStyleSheet?(e=>{let t="";for(let i of e.cssRules)t+=i.cssText;return de(t)})(s):s;var{is:He,defineProperty:Ie,getOwnPropertyDescriptor:We,getOwnPropertyNames:Ve,getOwnPropertySymbols:je,getPrototypeOf:Fe}=Object,B=globalThis,he=B.trustedTypes,Ze=he?he.emptyScript:"",Ye=B.reactiveElementPolyfillSupport,M=(s,e)=>s,Z={toAttribute(s,e){switch(e){case Boolean:s=s?Ze:null;break;case Object:case Array:s=s==null?s:JSON.stringify(s)}return s},fromAttribute(s,e){let t=s;switch(e){case Boolean:t=s!==null;break;case Number:t=s===null?null:Number(s);break;case Object:case Array:try{t=JSON.parse(s)}catch{t=null}}return t}},pe=(s,e)=>!He(s,e),ue={attribute:!0,type:String,converter:Z,reflect:!1,useDefault:!1,hasChanged:pe};Symbol.metadata??=Symbol("metadata"),B.litPropertyMetadata??=new WeakMap;var f=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=ue){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let i=Symbol(),o=this.getPropertyDescriptor(e,i,t);o!==void 0&&Ie(this.prototype,e,o)}}static getPropertyDescriptor(e,t,i){let{get:o,set:a}=We(this.prototype,e)??{get(){return this[t]},set(r){this[t]=r}};return{get:o,set(r){let c=o?.call(this);a?.call(this,r),this.requestUpdate(e,c,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??ue}static _$Ei(){if(this.hasOwnProperty(M("elementProperties")))return;let e=Fe(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(M("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(M("properties"))){let t=this.properties,i=[...Ve(t),...je(t)];for(let o of i)this.createProperty(o,t[o])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[i,o]of t)this.elementProperties.set(i,o)}this._$Eh=new Map;for(let[t,i]of this.elementProperties){let o=this._$Eu(t,i);o!==void 0&&this._$Eh.set(o,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let i=new Set(e.flat(1/0).reverse());for(let o of i)t.unshift(F(o))}else e!==void 0&&t.push(F(e));return t}static _$Eu(e,t){let i=t.attribute;return i===!1?void 0:typeof i=="string"?i:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let i of t.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return ce(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,i){this._$AK(e,i)}_$ET(e,t){let i=this.constructor.elementProperties.get(e),o=this.constructor._$Eu(e,i);if(o!==void 0&&i.reflect===!0){let a=(i.converter?.toAttribute!==void 0?i.converter:Z).toAttribute(t,i.type);this._$Em=e,a==null?this.removeAttribute(o):this.setAttribute(o,a),this._$Em=null}}_$AK(e,t){let i=this.constructor,o=i._$Eh.get(e);if(o!==void 0&&this._$Em!==o){let a=i.getPropertyOptions(o),r=typeof a.converter=="function"?{fromAttribute:a.converter}:a.converter?.fromAttribute!==void 0?a.converter:Z;this._$Em=o;let c=r.fromAttribute(t,a.type);this[o]=c??this._$Ej?.get(o)??c,this._$Em=null}}requestUpdate(e,t,i,o=!1,a){if(e!==void 0){let r=this.constructor;if(o===!1&&(a=this[e]),i??=r.getPropertyOptions(e),!((i.hasChanged??pe)(a,t)||i.useDefault&&i.reflect&&a===this._$Ej?.get(e)&&!this.hasAttribute(r._$Eu(e,i))))return;this.C(e,t,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,t,{useDefault:i,reflect:o,wrapped:a},r){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,r??t??this[e]),a!==!0||r!==void 0)||(this._$AL.has(e)||(this.hasUpdated||i||(t=void 0),this._$AL.set(e,t)),o===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[o,a]of this._$Ep)this[o]=a;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[o,a]of i){let{wrapped:r}=a,c=this[o];r!==!0||this._$AL.has(o)||c===void 0||this.C(o,void 0,a,c)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(t)):this._$EM()}catch(i){throw e=!1,this._$EM(),i}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(e){}firstUpdated(e){}};f.elementStyles=[],f.shadowRootOptions={mode:"open"},f[M("elementProperties")]=new Map,f[M("finalized")]=new Map,Ye?.({ReactiveElement:f}),(B.reactiveElementVersions??=[]).push("2.1.2");var te=globalThis,me=s=>s,H=te.trustedTypes,ge=H?H.createPolicy("lit-html",{createHTML:s=>s}):void 0,$e="$lit$",b=`lit$${Math.random().toFixed(9).slice(2)}$`,xe="?"+b,Ke=`<${xe}>`,A=document,N=()=>A.createComment(""),T=s=>s===null||typeof s!="object"&&typeof s!="function",se=Array.isArray,Ge=s=>se(s)||typeof s?.[Symbol.iterator]=="function",Y=`[ 	
\f\r]`,D=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,_e=/-->/g,ye=/>/g,k=RegExp(`>|${Y}(?:([^\\s"'>=/]+)(${Y}*=${Y}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),fe=/'/g,be=/"/g,we=/^(?:script|style|textarea|title)$/i,ie=s=>(e,...t)=>({_$litType$:s,strings:e,values:t}),n=ie(1),v=ie(2),ct=ie(3),E=Symbol.for("lit-noChange"),d=Symbol.for("lit-nothing"),ve=new WeakMap,S=A.createTreeWalker(A,129);function ke(s,e){if(!se(s)||!s.hasOwnProperty("raw"))throw Error("invalid template strings array");return ge!==void 0?ge.createHTML(e):e}var Je=(s,e)=>{let t=s.length-1,i=[],o,a=e===2?"<svg>":e===3?"<math>":"",r=D;for(let c=0;c<t;c++){let l=s[c],u,m,h=-1,_=0;for(;_<l.length&&(r.lastIndex=_,m=r.exec(l),m!==null);)_=r.lastIndex,r===D?m[1]==="!--"?r=_e:m[1]!==void 0?r=ye:m[2]!==void 0?(we.test(m[2])&&(o=RegExp("</"+m[2],"g")),r=k):m[3]!==void 0&&(r=k):r===k?m[0]===">"?(r=o??D,h=-1):m[1]===void 0?h=-2:(h=r.lastIndex-m[2].length,u=m[1],r=m[3]===void 0?k:m[3]==='"'?be:fe):r===be||r===fe?r=k:r===_e||r===ye?r=D:(r=k,o=void 0);let y=r===k&&s[c+1].startsWith("/>")?" ":"";a+=r===D?l+Ke:h>=0?(i.push(u),l.slice(0,h)+$e+l.slice(h)+b+y):l+b+(h===-2?c:y)}return[ke(s,a+(s[t]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),i]},O=class s{constructor({strings:e,_$litType$:t},i){let o;this.parts=[];let a=0,r=0,c=e.length-1,l=this.parts,[u,m]=Je(e,t);if(this.el=s.createElement(u,i),S.currentNode=this.el.content,t===2||t===3){let h=this.el.content.firstChild;h.replaceWith(...h.childNodes)}for(;(o=S.nextNode())!==null&&l.length<c;){if(o.nodeType===1){if(o.hasAttributes())for(let h of o.getAttributeNames())if(h.endsWith($e)){let _=m[r++],y=o.getAttribute(h).split(b),g=/([.?@])?(.*)/.exec(_);l.push({type:1,index:a,name:g[2],strings:y,ctor:g[1]==="."?G:g[1]==="?"?J:g[1]==="@"?X:R}),o.removeAttribute(h)}else h.startsWith(b)&&(l.push({type:6,index:a}),o.removeAttribute(h));if(we.test(o.tagName)){let h=o.textContent.split(b),_=h.length-1;if(_>0){o.textContent=H?H.emptyScript:"";for(let y=0;y<_;y++)o.append(h[y],N()),S.nextNode(),l.push({type:2,index:++a});o.append(h[_],N())}}}else if(o.nodeType===8)if(o.data===xe)l.push({type:2,index:a});else{let h=-1;for(;(h=o.data.indexOf(b,h+1))!==-1;)l.push({type:7,index:a}),h+=b.length-1}a++}}static createElement(e,t){let i=A.createElement("template");return i.innerHTML=e,i}};function L(s,e,t=s,i){if(e===E)return e;let o=i!==void 0?t._$Co?.[i]:t._$Cl,a=T(e)?void 0:e._$litDirective$;return o?.constructor!==a&&(o?._$AO?.(!1),a===void 0?o=void 0:(o=new a(s),o._$AT(s,t,i)),i!==void 0?(t._$Co??=[])[i]=o:t._$Cl=o),o!==void 0&&(e=L(s,o._$AS(s,e.values),o,i)),e}var K=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:i}=this._$AD,o=(e?.creationScope??A).importNode(t,!0);S.currentNode=o;let a=S.nextNode(),r=0,c=0,l=i[0];for(;l!==void 0;){if(r===l.index){let u;l.type===2?u=new z(a,a.nextSibling,this,e):l.type===1?u=new l.ctor(a,l.name,l.strings,this,e):l.type===6&&(u=new ee(a,this,e)),this._$AV.push(u),l=i[++c]}r!==l?.index&&(a=S.nextNode(),r++)}return S.currentNode=A,o}p(e){let t=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(e,i,t),t+=i.strings.length-2):i._$AI(e[t])),t++}},z=class s{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,i,o){this.type=2,this._$AH=d,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=i,this.options=o,this._$Cv=o?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=L(this,e,t),T(e)?e===d||e==null||e===""?(this._$AH!==d&&this._$AR(),this._$AH=d):e!==this._$AH&&e!==E&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):Ge(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==d&&T(this._$AH)?this._$AA.nextSibling.data=e:this.T(A.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:i}=e,o=typeof i=="number"?this._$AC(e):(i.el===void 0&&(i.el=O.createElement(ke(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===o)this._$AH.p(t);else{let a=new K(o,this),r=a.u(this.options);a.p(t),this.T(r),this._$AH=a}}_$AC(e){let t=ve.get(e.strings);return t===void 0&&ve.set(e.strings,t=new O(e)),t}k(e){se(this._$AH)||(this._$AH=[],this._$AR());let t=this._$AH,i,o=0;for(let a of e)o===t.length?t.push(i=new s(this.O(N()),this.O(N()),this,this.options)):i=t[o],i._$AI(a),o++;o<t.length&&(this._$AR(i&&i._$AB.nextSibling,o),t.length=o)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let i=me(e).nextSibling;me(e).remove(),e=i}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},R=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,i,o,a){this.type=1,this._$AH=d,this._$AN=void 0,this.element=e,this.name=t,this._$AM=o,this.options=a,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=d}_$AI(e,t=this,i,o){let a=this.strings,r=!1;if(a===void 0)e=L(this,e,t,0),r=!T(e)||e!==this._$AH&&e!==E,r&&(this._$AH=e);else{let c=e,l,u;for(e=a[0],l=0;l<a.length-1;l++)u=L(this,c[i+l],t,l),u===E&&(u=this._$AH[l]),r||=!T(u)||u!==this._$AH[l],u===d?e=d:e!==d&&(e+=(u??"")+a[l+1]),this._$AH[l]=u}r&&!o&&this.j(e)}j(e){e===d?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},G=class extends R{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===d?void 0:e}},J=class extends R{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==d)}},X=class extends R{constructor(e,t,i,o,a){super(e,t,i,o,a),this.type=5}_$AI(e,t=this){if((e=L(this,e,t,0)??d)===E)return;let i=this._$AH,o=e===d&&i!==d||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,a=e!==d&&(i===d||o);o&&this.element.removeEventListener(this.name,this,i),a&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},ee=class{constructor(e,t,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){L(this,e)}};var Xe=te.litHtmlPolyfillSupport;Xe?.(O,z),(te.litHtmlVersions??=[]).push("3.3.3");var Se=(s,e,t)=>{let i=t?.renderBefore??e,o=i._$litPart$;if(o===void 0){let a=t?.renderBefore??null;i._$litPart$=o=new z(e.insertBefore(N(),a),a,void 0,t??{})}return o._$AI(s),o};var oe=globalThis,$=class extends f{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Se(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return E}};$._$litElement$=!0,$.finalized=!0,oe.litElementHydrateSupport?.({LitElement:$});var et=oe.litElementPolyfillSupport;et?.({LitElement:$});(oe.litElementVersions??=[]).push("4.2.2");function I(s,e,t,i){return n`<dialog aria-labelledby="detail-title" @cancel=${()=>s._closeDetail()}>
    <div class="detail-header"><div><p class="eyebrow">${t}</p><h2 id="detail-title">${e}</h2></div><button autofocus @click=${()=>s._closeDetail()}>Close</button></div>
    ${i}
  </dialog>`}function re(s,e=!1){let t=s.points;if(!t.length)return n`<div class="trend-empty">No readings in the last 14 days</div>`;let i=e?600:160,o=e?150:48,a=t.map(g=>g.v),r=Math.min(...a),c=Math.max(...a)-r||Math.abs(r)*.05||1,l=t.map(g=>new Date(g.t).getTime()),u=l[l.length-1]-l[0]||1,m=g=>6+(l[g]-l[0])/u*(i-12),h=g=>o-8-(g-r)/c*(o-16),_=[],y="";return t.forEach((g,x)=>{x&&g.source_changed&&(_.push(y),y=""),y+=`${y?" L":"M"}${m(x)},${h(g.v)}`}),_.push(y),n`<svg class="sparkline" viewBox="0 0 ${i} ${o}" role="img" aria-label="Recorded trend over 14 days. Lines break when the source changes.">
    ${_.map(g=>v`<path d=${g}></path>`)}
    ${t.map((g,x)=>v`<circle cx=${m(x)} cy=${h(g.v)} r=${e?2.5:1.8}><title>${g.v} ${s.unit} · ${new Date(g.t).toLocaleString()}</title></circle>`)}
  </svg>`}function q(s,e){if(e.state==="source_changed")return"Source changed. Compare with care.";if(e.state==="conflict")return"Sources disagree. Review readings.";if(e.delta===null)return"More history needed for a comparison";let t=s._display(Math.abs(e.delta),e.unit),i=e.unit==="count"?0:1;if(Number(t.value.toFixed(i))===0)return"No visible change at this precision";let o=t.unit==="count"?"steps":t.unit==="%"?"percentage points":t.unit;return`${e.delta>0?"+":e.delta<0?"\u2212":""}${s._fmt(t.value,i)} ${o} \xB7 ${e.state==="steady"?"little change":e.delta>0?"up":"down"}`}function Ee(s,e){let t=e.current;return t?`${e.stale?"Older reading \xB7 ":"Observed "}${s._when(t.observed_at)}`:"No readings yet"}function Ae(s,e){return n`<button class="metric-row ${e.stale?"stale":""}" @click=${t=>s._openDetail(e.metric,t)}>
    <div><span class="metric-name">${s._label(e.metric)}</span><span class="metric-source">${e.current?s._providerName(e.current.provider):"Connect a source or log a reading"}</span></div>
    <div class="row-trend">${re(e)}</div>
    <div class="metric-value">${s._metricValue(e.current,e.unit==="count"?0:1)}<span class="metric-source">${Ee(s,e)}</span></div>
    <div class="row-change">${e.current?q(s,e):"No comparison yet"}${e.delta!==null?n`<span class="metric-source">${e.comparison_label}</span>`:d}</div>
    <span class="row-arrow" aria-hidden="true">›</span>
  </button>`}function Le(s){let e=s._overview;if(!e)return n`<p role="status">${s._loading?"Loading your health record\u2026":"Health data is unavailable."}</p>`;let t=e.metrics.filter(r=>r.current),i=t[0],o=t.filter(r=>r!==i),a=e.metrics.filter(r=>!r.current);return n`
    <div class="overview-actions"><button @click=${()=>s._openForm("measure")}>Log a measurement</button><button @click=${()=>s._openForm("workout")}>Log a workout</button></div>
    ${s._measurementForm()}${s._workoutForm()}
    ${i?n`<section class="lead-change ${i.stale?"stale":""}">
      <div class="lead-copy"><p class="eyebrow">${i.state==="changed"&&!i.stale?"A change in your record":i.state==="conflict"?"Worth a closer look":"Your latest readings"}</p>
        <h2>${s._label(i.metric)}</h2><div class="lead-value">${s._metricValue(i.current,i.unit==="count"?0:1)}</div>
        <p class="change-line">${q(s,i)}</p>
        ${i.delta!==null?n`<p class="sub">${i.comparison_label}</p>`:d}
        <p class="sub">${s._providerName(i.current.provider)} · ${Ee(s,i)}</p>
        <button class="primary" @click=${r=>s._openDetail(i.metric,r)}>Review ${s._label(i.metric).toLowerCase()}</button>
      </div><div class="lead-chart">${re(i,!0)}<span class="sub">Last 14 days · recorded readings</span></div>
    </section>`:n`<section class="intro-empty"><p class="eyebrow">Start with one reading</p><h2>Your health record starts here.</h2><p>Connect your scale or activity tracker in Health Assistant’s integration settings, or log a measurement above. Your history stays on this Home Assistant instance.</p><a href="/config/integrations/integration/health_assistant">Open integration settings</a></section>`}
    ${o.length?n`<section class="metric-section" aria-label="Health metrics"><div class="section-heading"><h2>The rest of your record</h2><span class="sub">Select a metric for readings and sources</span></div>${o.map(r=>Ae(s,r))}</section>`:d}
    ${a.length?n`<details class="missing-metrics"><summary>${a.length} ${a.length===1?"metric":"metrics"} without readings</summary><p class="sub">Connect a source, add a reading, or open a metric to restore an excluded record.</p>${a.map(r=>Ae(s,r))}</details>`:d}
    <section class="workout-section"><div class="section-heading"><h2>This week’s training</h2><span class="sub">${e.workout_count} ${e.workout_count===1?"workout":"workouts"} in the last 7 days</span></div>
      ${e.workouts.length?n`<div class="workout-strip">${e.workouts.map(r=>n`<article class="workout-item"><span class="eyebrow">${s._when(r.started_at)}</span><h3>${r.title}</h3><p>${s._fmt(r.duration_seconds/60,0)} min · ${r.workout_type}</p><span class="sub">${s._providerName(r.provider)}</span></article>`)}</div>`:n`<p class="empty-note">No workouts recorded this week. Connected workout sources and manual entries will appear here.</p>`}
    </section>
    <details class="source-status"><summary>Sources <span>${e.providers.filter(r=>r.degraded).length?"\xB7 needs attention":"\xB7 status"}</span></summary><p class="sub">Successful source operations and measurement times are different. A source can be working while its latest reading is old.</p>${e.providers.map(r=>n`<div class="source-row"><strong>${s._providerName(r.key)}</strong><span>${r.degraded?"Needs attention":r.had_error?"Working again":r.last_success?"Working":"Waiting for data"}</span><span class="sub">${r.last_success?`Last successful operation ${s._when(r.last_success)}`:"No successful operation since reload"}</span></div>`)}<a href="/config/integrations/integration/health_assistant">Manage sources in integration settings</a></details>
  `}function Re(s){if(!s._detailMetric)return d;let e=s._overview?.metrics.find(o=>o.metric===s._detailMetric),t=s._detail,i=t?.observation;return I(s,s._label(s._detailMetric),"Readings and sources",n`
    ${s._detailError?n`<p class="error" role="alert">${s._detailError}<button @click=${()=>s._loadDetail()}>Try again</button></p>`:d}
    ${e?n`<div class="detail-trend">${re(e,!0)}<p class="sub">${q(s,e)}${e.delta!==null?` \xB7 ${e.comparison_label}`:""}</p></div>`:d}
    ${s._detailLoading?n`<p role="status">Loading readings…</p>`:d}
    ${i?n`<section class="reading-detail"><div class="section-heading"><h3>${i.excluded?"Excluded reading":"Selected reading"}</h3><span class="reading-value">${s._metricValue(i)}</span></div><p>${new Date(i.observed_at).toLocaleString()} · ${s._providerName(i.provider)}</p>
      ${i.possible_duplicate?n`<p class="notice">Nearby sources may disagree. Review the original claims and nearby readings before changing anything.</p>`:d}
      ${i.excluded?n`<p class="notice">Kept in your history, excluded from summaries and trends.</p>`:d}
      <h4>Source claims</h4><p class="sub">The selected claim supplies this record’s value. Source priority resolves equivalent claims; nearby records are shown separately.</p>
      ${t.claims.map(o=>n`<div class="claim-row"><div><strong>${s._providerName(o.provider)}</strong><span class="metric-source">${o.selected?"Selected claim":"Retained claim"} · ${new Date(o.observed_at).toLocaleString()}</span><span class="source-id">${o.external_id}</span></div><span>${s._metricValue(o)}</span></div>`)}
      ${t.claim_count>t.claims.length?n`<p class="sub">Showing ${t.claims.length} of ${t.claim_count} claims.</p>`:d}
      ${t.nearby.length?n`<h4>Nearby readings</h4>${t.nearby.map(o=>n`<button class="record-button" ?disabled=${s._detailLoading} @click=${()=>s._loadDetail(o.id)}><span>${s._providerName(o.provider)} · ${s._when(o.observed_at)}</span><span>${s._metricValue(o)}</span></button>`)}`:d}
      ${s.hass.user?.is_admin?n`<div class="exclusion-control"><p class="sub">${i.excluded?"Restore this reading to summaries and trends.":"An incorrect reading can be excluded without deleting its source history. You can restore it later."}</p><button ?disabled=${!!s._busyId||s._detailLoading} @click=${()=>s._toggleExclusion()}>${s._busyId?"Saving\u2026":i.excluded?"Restore reading":"Exclude reading"}</button></div>`:n`<p class="sub">An administrator can exclude or restore incorrect readings.</p>`}
    </section>`:s._detailLoading?d:n`<p>No ${s._showExcluded?"excluded ":""}readings to show.</p>`}
    <section class="record-history"><div class="section-heading"><h3>Browse readings</h3><label class="excluded-toggle"><input type="checkbox" .checked=${s._showExcluded} @change=${o=>{s._showExcluded=o.target.checked,s._detail=void 0,s._loadDetail()}} /> Excluded only</label></div><p class="sub">Most recently added first</p>
    ${s._records.map(o=>n`<button class="record-button ${i?.id===o.id?"selected":""}" ?disabled=${s._detailLoading} @click=${()=>s._loadDetail(o.id)}><span>${new Date(o.observed_at).toLocaleString()}<span class="metric-source">${s._providerName(o.provider)}</span></span><span>${s._metricValue(o)}</span></button>`)}
    ${s._nextRecord?n`<button ?disabled=${s._detailLoading} @click=${()=>s._loadDetail(i?.id,!0)}>Load older readings</button>`:d}</section>
  `)}var Ce=w`
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
`;var Me="M181 91L180 110Q148 108 135 130L119 184L109 232L87 311L83 330Q85 343 96 347L111 333L128 283L142 224L153 186L158 240L151 282Q147 309 156 338L163 413L167 489L166 542L155 577Q151 589 165 591L184 587L190 543L193 476L198 407L200 350L202 407L207 476L210 543L216 587L235 591Q249 589 245 577L234 542L233 489L237 413L244 338Q253 309 249 282L242 240L247 186L258 224L272 283L289 333L304 347Q315 343 317 330L313 311L291 232L281 184L265 130Q252 108 220 110L219 91Z",De=[{key:"shoulders",label:"Shoulders",sides:["front","back"],path:"M164 116Q145 116 137 138L129 168Q143 170 152 150Z"},{key:"chest",label:"Chest",sides:["front"],path:"M169 126Q158 137 157 156Q169 171 188 174Q196 176 196 166L196 139Q188 131 169 126Z"},{key:"biceps",label:"Biceps",sides:["front"],path:"M128 176Q136 172 143 176Q142 199 132 221Q126 232 120 236Q113 233 115 225Z"},{key:"triceps",label:"Triceps",sides:["back"],path:"M128 176Q136 172 143 176Q142 199 132 221Q126 232 120 236Q113 233 115 225Z"},{key:"forearms",label:"Forearms",sides:["front","back"],path:"M113 245Q119 241 125 240Q123 267 114 284L100 320Q95 323 92 317Z"},{key:"core",label:"Core",sides:["front"],path:"M160 175Q177 184 190 184L196 182L196 259Q183 270 167 275Q163 256 160 236Q157 203 160 175Z"},{key:"back",label:"Back",sides:["back"],path:"M167 122Q182 125 196 134L196 180Q184 190 169 193Q158 177 157 158ZM158 177L168 202Q184 198 196 191L196 248Q182 260 166 269Q159 250 158 231Z"},{key:"glutes",label:"Glutes",sides:["back"],path:"M165 280Q181 276 196 277L196 308Q193 321 184 326Q169 328 164 320Q154 309 165 280Z"},{key:"quads",label:"Quads",sides:["front"],path:"M163 295Q175 291 188 291Q194 316 193 337Q191 376 186 403Q180 414 171 413Q161 387 162 355Q155 325 163 295Z"},{key:"hamstrings",label:"Hamstrings",sides:["back"],path:"M164 338Q176 343 189 337Q192 365 186 410Q180 420 170 416Q163 397 163 370Z"},{key:"calves",label:"Calves",sides:["back"],path:"M171 429Q178 433 185 427Q190 454 183 490L177 537Q173 540 170 536L169 486Q163 455 171 429Z"}];function W(s,e){(s.key==="Enter"||s.key===" ")&&(s.preventDefault(),e(s))}function tt(s){let e=s._body.regions;return n`<svg class="body-figure" viewBox="0 0 400 620" aria-label=${`Body, ${s._bodySide} view. Choose a muscle region to see recorded sets.`}>
    <ellipse cx="200" cy="59" rx="28" ry="36" class="body-outline" />
    <path d=${Me} class="body-outline" />
    ${De.filter(t=>t.sides.includes(s._bodySide)).map(t=>{let i=e.find(a=>a.key===t.key),o=i?.heat||0;return v`<g class="body-region ${o?"recorded":""}" style=${`--region-heat: ${.18+o*.82}`} role="button" tabindex="0" aria-label=${`${t.label}, ${i?.recorded_sets||0} recorded sets`} @click=${a=>s._openRegion(t.key,a)} @keydown=${a=>W(a,r=>s._openRegion(t.key,r))}>
        <title>${t.label}</title><path d=${t.path}/><path d=${t.path} transform="translate(400 0) scale(-1 1)"/>
      </g>`})}
    <g class="body-anchor" role="button" tabindex="0" aria-label="Body measurements: weight, body fat and lean mass" @click=${t=>s._openRegion("measurements",t)} @keydown=${t=>W(t,i=>s._openRegion("measurements",i))}><circle cx="200" cy="226" r="15"/><path d="M194 226h12M200 220v12"/></g>
    <g class="body-dormant" role="button" tabindex="0" aria-label="Sleep, not available yet" @click=${t=>s._openRegion("sleep",t)} @keydown=${t=>W(t,i=>s._openRegion("sleep",i))}><circle cx="200" cy="59" r="20"/><path d="M204 48a12 12 0 1 0 7 19a11 11 0 0 1 -7 -19Z"/></g>
    ${s._bodySide==="front"?v`<g class="body-dormant" role="button" tabindex="0" aria-label="Heart, not available yet" @click=${t=>s._openRegion("heart",t)} @keydown=${t=>W(t,i=>s._openRegion("heart",i))}><circle cx="200" cy="148" r="17"/><path d="M200 157C182 146 188 134 196 142L200 146L204 142C212 134 218 146 200 157Z"/></g>`:d}
  </svg>`}function Ne(s){return s._overview.metrics.filter(e=>["weight","body_fat_percentage","lean_mass"].includes(e.metric)).map(e=>n`
    <button class="body-measurement ${e.stale?"stale":""}" @click=${t=>s._openDetail(e.metric,t)}>
      <span class="metric-name">${s._label(e.metric)}</span><span class="body-measurement-value">${e.current?s._metricValue(e.current):"No reading yet"}</span>
      <span class="metric-source">${e.current?`${s._providerName(e.current.provider)} \xB7 ${e.stale?"Older reading \xB7 ":""}${s._when(e.current.observed_at)}`:"Connect a source or log a reading"}</span>
      <span class="body-change">${q(s,e)}</span>
    </button>`)}function Te(s){let e=s._body;return e?n`<section class="body-intro"><div><p class="eyebrow">Experimental</p><h2>Your recorded week</h2><p class="sub">${e.workout_count} completed ${e.workout_count===1?"workout":"workouts"} in the last seven days. Choose a region to see its sets.</p></div><button @click=${()=>{s._bodySide=s._bodySide==="front"?"back":"front"}}>Show ${s._bodySide==="front"?"back":"front"}</button></section>
    ${s._bodyError?n`<p class="error" role="alert">${s._bodyError}<button @click=${()=>s._loadBody()}>Try again</button></p>`:d}
    ${e.truncated||e.incomplete_workouts?n`<p class="notice">${e.truncated?`Showing the latest ${e.workouts.length} of ${e.workout_count} workouts. `:""}${e.incomplete_workouts?`${e.incomplete_workouts} ${e.incomplete_workouts===1?"workout has":"workouts have"} incomplete exercise detail.`:""} Colors reflect the usable records shown here.</p>`:d}
    <div class="body-layout"><div class="body-art"><p class="body-side" aria-live="polite">${s._bodySide}</p>${tt(s)}<div class="body-legend"><span>Fewer</span><span class="heat-scale" aria-hidden="true"></span><span>More</span></div><p class="body-legend-copy">Recent recorded sets, fading over seven days.<br/>Color is relative to your most active region.</p></div>
    <aside class="body-context"><section><p class="eyebrow">Body measurements</p><div class="body-measurements">${Ne(s)}</div></section>
      <section class="body-future"><p class="eyebrow">Still to come</p><button @click=${t=>s._openRegion("sleep",t)}><span class="future-symbol" aria-hidden="true">◔</span><span>Sleep<span class="metric-source">Not available yet</span></span></button><button @click=${t=>s._openRegion("heart",t)}><span class="future-symbol" aria-hidden="true">♡</span><span>Heart<span class="metric-source">Not available yet</span></span></button></section>
      ${e.workouts_without_sets?n`<p class="sub">${e.workouts_without_sets} ${e.workouts_without_sets===1?"workout has":"workouts have"} no usable non-warmup sets. Workout summaries remain available below.</p>`:d}
      ${e.unmapped_count?n`<details class="body-unmapped"><summary>${e.unmapped_count} unmapped exercise ${e.unmapped_count===1?"entry":"entries"}</summary><p class="sub">These names aren't in the exercise map yet. Their sets don't color the figure.</p><ul>${e.unmapped.map(t=>n`<li>${t.name}${t.occurrences>1?` (${t.occurrences})`:""}</li>`)}</ul><p class="sub">Up to 20 names shown. Open a workout below for its exercise detail.</p></details>`:d}
    </aside></div>
    <section class="body-workouts"><div class="section-heading"><h2>Recorded workouts</h2><span class="sub">Last seven days</span></div>${e.workouts.length?e.workouts.map(t=>Oe(s,t)):n`<p class="empty-note">No workouts recorded this week. A source with exercise and set detail will light up the figure as completed workouts arrive.</p>`}</section>`:s._bodyError?n`<p class="error" role="alert">${s._bodyError}<button @click=${()=>s._loadBody()}>Try again</button></p>`:n`<p role="status">Loading Body view…</p>`}function Oe(s,e){return n`<button class="record-button" @click=${t=>s._openWorkout(e.id,t)}><span>${e.title}<span class="metric-source">${s._providerName(e.provider)} · ${new Date(e.ended_at).toLocaleString()}</span></span><span>${e.recorded_sets} sets<span class="metric-source">${s._fmt(e.duration_seconds/60,0)} min</span></span></button>`}function st(s,e){let t=[];if(e.reps!==void 0&&t.push(`${s._fmt(e.reps,0)} reps`),e.weight_kg!==void 0){let i=s._display(e.weight_kg,"kg");t.push(`${s._fmt(i.value)} ${i.unit}`)}if(e.duration_seconds!==void 0&&t.push(`${s._fmt(e.duration_seconds,0)} sec`),e.distance_m!==void 0){let i=s._display(e.distance_m,"m");t.push(`${s._fmt(i.value)} ${i.unit}`)}return t.join(" \xB7 ")}function ze(s){if(!s._bodyRegion)return d;let e=s._bodyRegion,t=s._body,i=t?.regions.find(r=>r.key===e),o=i?.label||{measurements:"Body measurements",sleep:"Sleep",heart:"Heart",workout:"Workout"}[e],a;if(s._workoutId){let r=s._workoutDetail;o=r?.title||"Workout",a=n`${s._workoutLoading?n`<p role="status">Loading workout…</p>`:d}
      ${s._workoutError?n`<p class="error" role="alert">${s._workoutError}<button @click=${()=>s._loadWorkout(s._workoutId)}>Try again</button></p>`:d}
      ${r?n`<p>${s._providerName(r.provider)} · ${new Date(r.ended_at).toLocaleString()}</p><p class="sub">${s._fmt(r.duration_seconds/60,0)} min · ${r.workout_type}</p><p class="source-id">Source record: ${r.source}</p>
        ${r.incomplete?n`<p class="notice">Some exercise detail is incomplete or exceeds this view's limits. The original workout is kept in your history.</p>`:d}
        ${r.exercises.length?r.exercises.map(c=>n`<details class="exercise-detail"><summary>${c.name}<span>${c.recorded_sets} sets</span></summary><p class="sub">${c.regions.length?c.regions.map(l=>t.regions.find(u=>u.key===l)?.label||l).join(", "):"Unmapped exercise"}</p>${c.notes?n`<p class="exercise-notes">${c.notes}</p>`:d}<ol>${c.sets.map(l=>n`<li><span>${st(s,l)}</span><span class="sub">${l.warmup?"Warmup, not counted":l.type}</span></li>`)}</ol></details>`):n`<p>No usable exercise detail was recorded for this workout.</p>`}`:d}`}else if(e==="measurements")a=n`<p class="sub">The same canonical readings and trends as Overview. Choose a metric to inspect its sources.</p>${Ne(s)}`;else if(e==="sleep"||e==="heart")a=n`<p>Not available yet.</p><p class="sub">This region is reserved for a future ${e==="sleep"?"sleep":"heart data"} view.</p>`;else{let r=t.workouts.filter(c=>c.regions.includes(e));a=n`<p class="region-count">${i?.recorded_sets||0}<span> recorded sets</span></p><p class="sub">Non-warmup sets from the last seven days. Color fades with time and is relative to the most active region.</p>${r.length?r.map(c=>Oe(s,c)):n`<p>No mapped sets for this region in the recorded week.</p>`}`}return I(s,o,"Training and sources",a)}var qe=w`
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
`;var it=2.204622621848776,ot=1/1609.344,V=[{key:"weight",label:"Weight"},{key:"body_fat_percentage",label:"Body fat"},{key:"lean_mass",label:"Lean mass"},{key:"steps",label:"Steps"},{key:"distance",label:"Distance"},{key:"active_energy",label:"Active energy"}],rt=[7,30,90],ae={ha_entity:"Home Assistant sensors",manual:"Manual entries",withings:"Withings",fitbit:"Fitbit",hevy:"Hevy"},ne=class extends ${static properties={hass:{attribute:!1},narrow:{type:Boolean},panel:{attribute:!1},_overview:{state:!0},_body:{state:!0},_bodyError:{state:!0},_bodySide:{state:!0},_bodyRegion:{state:!0},_workoutId:{state:!0},_workoutDetail:{state:!0},_workoutLoading:{state:!0},_workoutError:{state:!0},_loading:{state:!0},_detailMetric:{state:!0},_detail:{state:!0},_records:{state:!0},_showExcluded:{state:!0},_detailError:{state:!0},_detailLoading:{state:!0},_busyId:{state:!0},_series:{state:!0},_tab:{state:!0},_metric:{state:!0},_days:{state:!0},_error:{state:!0},_form:{state:!0},_saving:{state:!0}};constructor(){super(),this._tab="overview",this._metric="weight",this._days=30,this._form=null,this._saving=!1,this._loadedOnce=!1,this._showExcluded=!1,this._records=[],this._request=0,this._detailRequest=0,this._dialogSession=0,this._bodySide="front",this._bodyRequest=0,this._workoutRequest=0}get _domain(){return this.panel&&this.panel.config&&this.panel.config.domain||"health_assistant"}get _imperial(){return!!(this.hass&&this.hass.config&&this.hass.config.unit_system&&this.hass.config.unit_system.length==="mi")}updated(e){if(e.has("hass")&&this.hass&&!this._loadedOnce){this._loadedOnce=!0;try{let t=window.localStorage.getItem(this._viewPreferenceKey);["overview","body","trends"].includes(t)&&(this._tab=t)}catch{}this._refresh()}}connectedCallback(){super.connectedCallback(),this._timer=window.setInterval(()=>{this.hass&&!this._loading&&this._refresh()},6e4)}disconnectedCallback(){super.disconnectedCallback(),window.clearInterval(this._timer)}async _refresh(){let e=++this._request;this._loading=!0,this._error=void 0;try{let t=await this.hass.callWS({type:`${this._domain}/overview`});e===this._request&&(this._overview=t),this._tab==="trends"&&await this._loadSeries(),this._tab==="body"&&await this._loadBody()}catch{e===this._request&&(this._error="Health data could not refresh. Check the integration and try again.")}finally{e===this._request&&(this._loading=!1)}}_providerName(e){return ae[e]||this._overview?.providers.find(t=>t.key===e)?.name||e.replaceAll("_"," ")}_label(e){return V.find(t=>t.key===e)?.label||e}async _openDetail(e,t){let i=++this._dialogSession;if(this._detailRequest++,this._workoutRequest++,this.shadowRoot.querySelector("dialog")?.open||(this._opener=t?.currentTarget),this._bodyRegion=void 0,this._detailMetric=e,this._detail=void 0,this._showExcluded=!1,this._records=[],await this.updateComplete,i!==this._dialogSession)return;let o=this.shadowRoot.querySelector("dialog");o.open||o.showModal(),await this._loadDetail()}_closeDetail(){this._dialogSession++,this._detailRequest++,this._workoutRequest++,this.shadowRoot.querySelector("dialog")?.close(),this._detailMetric=void 0,this._bodyRegion=void 0,this._workoutId=void 0,this._opener?.focus()}async _loadDetail(e,t=!1){let i=++this._detailRequest,o=this._detailMetric;if(!o)return;this._detailLoading=!0,this._detailError=void 0;let a=this._overview?.metrics.find(r=>r.metric===o)?.current;try{let r=await this.hass.callWS({type:`${this._domain}/observations`,metric:o,excluded:this._showExcluded,limit:20,...t&&this._nextRecord?{before_id:this._nextRecord}:{}}),c=e||(this._showExcluded?r.observations[0]?.id:a?.id),l=c?await this.hass.callWS({type:`${this._domain}/observation_detail`,observation_id:c}):void 0;if(i!==this._detailRequest)return;this._records=t?[...this._records,...r.observations]:r.observations,this._nextRecord=r.next_before_id,this._detail=l}catch{i===this._detailRequest&&(this._detailError="That reading could not load. It may have changed during a sync. Try again.")}finally{i===this._detailRequest&&(this._detailLoading=!1)}}async _toggleExclusion(){let e=this._detail?.observation;if(!e||this._busyId)return;let t=this._dialogSession,i=this._detailRequest,o=()=>t===this._dialogSession&&i===this._detailRequest;this._busyId=e.id,this._detailError=void 0;try{await this.hass.callWS({type:`${this._domain}/observation_exclusion`,observation_id:e.id,excluded:!e.excluded}),await this._refresh(),o()&&(i++,await this._loadDetail(e.id))}catch{o()&&(this._detailError="The reading could not be changed. Refresh and try again.")}finally{this._busyId=void 0,await this.updateComplete,o()&&this.shadowRoot.querySelector(".exclusion-control button")?.focus()}}async _loadSeries(){let e=(this._seriesRequest||0)+1;this._seriesRequest=e,this._series=void 0;try{let t=await this.hass.callWS({type:`${this._domain}/time_series`,metric:this._metric,days:this._days});e===this._seriesRequest&&(this._series=t)}catch{e===this._seriesRequest&&(this._error="Trend data could not load. Try refreshing.")}}get _viewPreferenceKey(){return`${this._domain}:${this.hass?.user?.id||"local"}:view`}async _loadBody(){let e=++this._bodyRequest;this._bodyError=void 0;try{let t=await this.hass.callWS({type:`${this._domain}/body`});e===this._bodyRequest&&(this._body=t)}catch{e===this._bodyRequest&&(this._bodyError="Body data could not refresh. Try again.")}}async _openRegion(e,t){let i=++this._dialogSession;if(this._detailRequest++,this._workoutRequest++,this.shadowRoot.querySelector("dialog")?.open||(this._opener=t?.currentTarget),this._detailMetric=void 0,this._bodyRegion=e,this._workoutId=void 0,this._workoutDetail=void 0,this._workoutError=void 0,await this.updateComplete,i!==this._dialogSession)return;let o=this.shadowRoot.querySelector("dialog");return o.open||o.showModal(),i}async _openWorkout(e,t){await this._openRegion("workout",t)===this._dialogSession&&await this._loadWorkout(e)}async _loadWorkout(e){let t=++this._workoutRequest,i=this._dialogSession;this._workoutId=e,this._workoutDetail=void 0,this._workoutLoading=!0,this._workoutError=void 0;try{let o=await this.hass.callWS({type:`${this._domain}/workout_detail`,workout_id:e});t===this._workoutRequest&&i===this._dialogSession&&(this._workoutDetail=o)}catch{t===this._workoutRequest&&i===this._dialogSession&&(this._workoutError="That workout could not load. Try again.")}finally{t===this._workoutRequest&&i===this._dialogSession&&(this._workoutLoading=!1)}}_setTab(e){this._tab=e;try{window.localStorage.setItem(this._viewPreferenceKey,e)}catch{}e==="trends"?this._loadSeries():this._refresh()}_setMetric(e){this._metric=e,this._loadSeries()}_setDays(e){this._days=e,this._loadSeries()}_display(e,t){return e==null?null:t==="kg"&&this._imperial?{value:e*it,unit:"lb"}:t==="m"&&this._imperial?{value:e*ot,unit:"mi"}:t==="m"&&e>=1e3?{value:e/1e3,unit:"km"}:{value:e,unit:t}}_fmt(e,t=1){return new Intl.NumberFormat(void 0,{maximumFractionDigits:t}).format(e)}_when(e){let t=new Date(e),o=Math.floor((new Date-t)/864e5);return o<=0?t.toLocaleTimeString(void 0,{hour:"numeric",minute:"2-digit"}):o===1?"yesterday":o<7?`${o} days ago`:t.toLocaleDateString()}_metricValue(e,t=1){if(!e)return n`<span class="empty-value">no data</span>`;let i=this._display(e.value,e.unit),o=i.unit==="count"?d:n`<span class="unit">${i.unit}</span>`;return n`<span class="value">${this._fmt(i.value,t)}</span>${o}`}_defaultUnit(e){return e==="weight"||e==="lean_mass"?this._imperial?"lb":"kg":e==="distance"?this._imperial?"mi":"km":e==="body_fat_percentage"?"%":e==="active_energy"?"kcal":""}_localNow(e=0){let t=new Date(Date.now()-e*6e4),i=o=>String(o).padStart(2,"0");return`${t.getFullYear()}-${i(t.getMonth()+1)}-${i(t.getDate())}T${i(t.getHours())}:${i(t.getMinutes())}`}_openForm(e){this._error=void 0,this._form=this._form===e?null:e}_formValue(e){let t=this.shadowRoot.getElementById(e);return t?t.value.trim():""}async _submitMeasurement(e){e.preventDefault();let t=Number(this._formValue("m-value"));if(!Number.isFinite(t)){this._error="Enter a numeric value";return}let o={metric:this._formValue("m-metric"),value:t},a=this._formValue("m-unit");a&&a!=="count"&&(o.unit=a);let r=this._formValue("m-when");r&&(o.observed_at=new Date(r).toISOString()),await this._callAction("add_observation",o)}async _submitWorkout(e){e.preventDefault();let t=this._formValue("w-type"),i=this._formValue("w-start"),o=this._formValue("w-end");if(!t||!i||!o){this._error="Workout type, start, and end are required";return}let a={workout_type:t,start:new Date(i).toISOString(),end:new Date(o).toISOString()},r=this._formValue("w-title");r&&(a.title=r);let c=this._formValue("w-energy");c&&(a.energy_kcal=Number(c));let l=this._formValue("w-distance");l&&(a.distance=Number(l),a.distance_unit=this._imperial?"mi":"km"),await this._callAction("add_workout",a)}async _callAction(e,t){this._saving=!0,this._error=void 0;try{await this.hass.callService(this._domain,e,t),this._form=null,await this._refresh()}catch(i){this._error=i&&i.message||"Unable to save"}finally{this._saving=!1}}_measurementForm(){return this._form!=="measure"?d:n`
      <form class="entry" @submit=${this._submitMeasurement}>
        <label>Metric
          <select id="m-metric" @change=${e=>{let t=this.shadowRoot.getElementById("m-unit");t&&(t.value=this._defaultUnit(e.target.value))}}>
            ${V.map(e=>n`<option value=${e.key}>${e.label}</option>`)}
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
    `}_workoutForm(){return this._form!=="workout"?d:n`
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
    `}_renderOverview(){return Le(this)}_chart(){let e=this._series;if(!e)return n`<p role="status">Loading trend…</p>`;if(e.points.length===0)return n`<p class="empty-value">
        No ${this._metricLabel().toLowerCase()} data in the last ${this._days} days.
      </p>`;let t=640,i=260,o={left:54,right:16,top:16,bottom:34},a=e.points.map(p=>({time:new Date(p.t).getTime(),shown:this._display(p.v,e.unit),provider:p.provider})),r=a[0].shown.unit,c=a.map(p=>p.shown.value),l=a.map(p=>p.time),u=Math.min(...c),m=Math.max(...c),h=m-u||Math.abs(m)*.1||1,_=Math.min(...l),y=Math.max(...l),g=y-_||1,x=p=>o.left+(p-_)/g*(t-o.left-o.right),P=p=>i-o.bottom-(p-(u-h*.05))/(h*1.1)*(i-o.top-o.bottom),Pe=a.map((p,Be)=>`${Be===0?"M":"L"}${x(p.time).toFixed(1)},${P(p.shown.value).toFixed(1)}`).join(" "),Qe=a.length<=120?a.map(p=>v`<circle cx="${x(p.time)}" cy="${P(p.shown.value)}" r="3">
                <title>${this._fmt(p.shown.value)} ${r} · ${new Date(p.time).toLocaleString()} · ${ae[p.provider]||p.provider}</title>
              </circle>`):d,Ue=[...new Set(e.points.map(p=>p.provider))].map(p=>ae[p]||p);return n`
      <svg viewBox="0 0 ${t} ${i}" role="img">
        <line class="axis" x1="${o.left}" y1="${i-o.bottom}" x2="${t-o.right}" y2="${i-o.bottom}"></line>
        <line class="axis" x1="${o.left}" y1="${o.top}" x2="${o.left}" y2="${i-o.bottom}"></line>
        <text class="tick" x="${o.left-8}" y="${P(m)+4}" text-anchor="end">${this._fmt(m)}</text>
        <text class="tick" x="${o.left-8}" y="${P(u)+4}" text-anchor="end">${this._fmt(u)}</text>
        <text class="tick" x="${o.left}" y="${i-10}">${new Date(_).toLocaleDateString()}</text>
        <text class="tick" x="${t-o.right}" y="${i-10}" text-anchor="end">${new Date(y).toLocaleDateString()}</text>
        <path class="line" d="${Pe}"></path>
        ${Qe}
      </svg>
      <div class="sub caption">
        ${e.points.length} points${r==="count"?"":` (${r})`}
        ${e.downsampled?" \xB7 downsampled":""} · from ${Ue.join(", ")}
      </div>
    `}_metricLabel(){let e=V.find(t=>t.key===this._metric);return e?e.label:this._metric}_renderTrends(){return n`
      <div class="card wide">
        <div class="selector">
          ${V.map(e=>n`<button
              class=${this._metric===e.key?"active":""}
              @click=${()=>this._setMetric(e.key)}
            >
              ${e.label}
            </button>`)}
        </div>
        <div class="selector">
          ${rt.map(e=>n`<button
              class=${this._days===e?"active":""}
              @click=${()=>this._setDays(e)}
            >
              ${e} days
            </button>`)}
        </div>
        ${this._chart()}
      </div>
    `}render(){return n`
      <div class="wrapper">
        <header>
          <div class="header-identity">${this.narrow?n`<button aria-label="Open sidebar" @click=${()=>this.dispatchEvent(new window.Event("hass-toggle-menu",{bubbles:!0,composed:!0}))}>Menu</button>`:d}<div><h1>Health</h1><p class="page-subtitle">Your record, at a glance</p></div></div>
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
          </nav>
        </header>
        ${this._error?n`<div class="card error">${this._error}</div>`:d}
        ${this._tab==="overview"?this._renderOverview():this._tab==="body"?Te(this):this._renderTrends()}
        ${this._bodyRegion?ze(this):Re(this)}
      </div>
    `}static styles=[Ce,qe,w`
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
  `]};customElements.get("health-assistant-panel")||customElements.define("health-assistant-panel",ne);
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
