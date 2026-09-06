var U=globalThis,H=U.ShadowRoot&&(U.ShadyCSS===void 0||U.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,B=Symbol(),at=new WeakMap,C=class{constructor(t,e,s){if(this._$cssResult$=!0,s!==B)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(H&&t===void 0){let s=e!==void 0&&e.length===1;s&&(t=at.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),s&&at.set(e,t))}return t}toString(){return this.cssText}},nt=r=>new C(typeof r=="string"?r:r+"",void 0,B),M=(r,...t)=>{let e=r.length===1?r[0]:t.reduce((s,i,a)=>s+(o=>{if(o._$cssResult$===!0)return o.cssText;if(typeof o=="number")return o;throw Error("Value passed to 'css' function must be a 'css' function result: "+o+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+r[a+1],r[0]);return new C(e,r,B)},lt=(r,t)=>{if(H)r.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let s=document.createElement("style"),i=U.litNonce;i!==void 0&&s.setAttribute("nonce",i),s.textContent=e.cssText,r.appendChild(s)}},j=H?r=>r:r=>r instanceof CSSStyleSheet?(t=>{let e="";for(let s of t.cssRules)e+=s.cssText;return nt(e)})(r):r;var{is:Tt,defineProperty:Lt,getOwnPropertyDescriptor:Ot,getOwnPropertyNames:Pt,getOwnPropertySymbols:zt,getPrototypeOf:Ut}=Object,q=globalThis,ct=q.trustedTypes,Ht=ct?ct.emptyScript:"",qt=q.reactiveElementPolyfillSupport,R=(r,t)=>r,W={toAttribute(r,t){switch(t){case Boolean:r=r?Ht:null;break;case Object:case Array:r=r==null?r:JSON.stringify(r)}return r},fromAttribute(r,t){let e=r;switch(t){case Boolean:e=r!==null;break;case Number:e=r===null?null:Number(r);break;case Object:case Array:try{e=JSON.parse(r)}catch{e=null}}return e}},ht=(r,t)=>!Tt(r,t),dt={attribute:!0,type:String,converter:W,reflect:!1,useDefault:!1,hasChanged:ht};Symbol.metadata??=Symbol("metadata"),q.litPropertyMetadata??=new WeakMap;var v=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=dt){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let s=Symbol(),i=this.getPropertyDescriptor(t,s,e);i!==void 0&&Lt(this.prototype,t,i)}}static getPropertyDescriptor(t,e,s){let{get:i,set:a}=Ot(this.prototype,t)??{get(){return this[e]},set(o){this[e]=o}};return{get:i,set(o){let d=i?.call(this);a?.call(this,o),this.requestUpdate(t,d,s)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??dt}static _$Ei(){if(this.hasOwnProperty(R("elementProperties")))return;let t=Ut(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(R("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(R("properties"))){let e=this.properties,s=[...Pt(e),...zt(e)];for(let i of s)this.createProperty(i,e[i])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[s,i]of e)this.elementProperties.set(s,i)}this._$Eh=new Map;for(let[e,s]of this.elementProperties){let i=this._$Eu(e,s);i!==void 0&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let s=new Set(t.flat(1/0).reverse());for(let i of s)e.unshift(j(i))}else t!==void 0&&e.push(j(t));return e}static _$Eu(t,e){let s=e.attribute;return s===!1?void 0:typeof s=="string"?s:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let s of e.keys())this.hasOwnProperty(s)&&(t.set(s,this[s]),delete this[s]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return lt(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,s){this._$AK(t,s)}_$ET(t,e){let s=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,s);if(i!==void 0&&s.reflect===!0){let a=(s.converter?.toAttribute!==void 0?s.converter:W).toAttribute(e,s.type);this._$Em=t,a==null?this.removeAttribute(i):this.setAttribute(i,a),this._$Em=null}}_$AK(t,e){let s=this.constructor,i=s._$Eh.get(t);if(i!==void 0&&this._$Em!==i){let a=s.getPropertyOptions(i),o=typeof a.converter=="function"?{fromAttribute:a.converter}:a.converter?.fromAttribute!==void 0?a.converter:W;this._$Em=i;let d=o.fromAttribute(e,a.type);this[i]=d??this._$Ej?.get(i)??d,this._$Em=null}}requestUpdate(t,e,s,i=!1,a){if(t!==void 0){let o=this.constructor;if(i===!1&&(a=this[t]),s??=o.getPropertyOptions(t),!((s.hasChanged??ht)(a,e)||s.useDefault&&s.reflect&&a===this._$Ej?.get(t)&&!this.hasAttribute(o._$Eu(t,s))))return;this.C(t,e,s)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:s,reflect:i,wrapped:a},o){s&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,o??e??this[t]),a!==!0||o!==void 0)||(this._$AL.has(t)||(this.hasUpdated||s||(e=void 0),this._$AL.set(t,e)),i===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[i,a]of this._$Ep)this[i]=a;this._$Ep=void 0}let s=this.constructor.elementProperties;if(s.size>0)for(let[i,a]of s){let{wrapped:o}=a,d=this[i];o!==!0||this._$AL.has(i)||d===void 0||this.C(i,void 0,a,d)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(s=>s.hostUpdate?.()),this.update(e)):this._$EM()}catch(s){throw t=!1,this._$EM(),s}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};v.elementStyles=[],v.shadowRootOptions={mode:"open"},v[R("elementProperties")]=new Map,v[R("finalized")]=new Map,qt?.({ReactiveElement:v}),(q.reactiveElementVersions??=[]).push("2.1.2");var Q=globalThis,ut=r=>r,I=Q.trustedTypes,pt=I?I.createPolicy("lit-html",{createHTML:r=>r}):void 0,$t="$lit$",b=`lit$${Math.random().toFixed(9).slice(2)}$`,bt="?"+b,It=`<${bt}>`,A=document,D=()=>A.createComment(""),T=r=>r===null||typeof r!="object"&&typeof r!="function",X=Array.isArray,Vt=r=>X(r)||typeof r?.[Symbol.iterator]=="function",F=`[ 	
\f\r]`,N=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,mt=/-->/g,gt=/>/g,x=RegExp(`>|${F}(?:([^\\s"'>=/]+)(${F}*=${F}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),_t=/'/g,ft=/"/g,yt=/^(?:script|style|textarea|title)$/i,tt=r=>(t,...e)=>({_$litType$:r,strings:t,values:e}),l=tt(1),P=tt(2),Xt=tt(3),S=Symbol.for("lit-noChange"),c=Symbol.for("lit-nothing"),vt=new WeakMap,w=A.createTreeWalker(A,129);function xt(r,t){if(!X(r)||!r.hasOwnProperty("raw"))throw Error("invalid template strings array");return pt!==void 0?pt.createHTML(t):t}var Bt=(r,t)=>{let e=r.length-1,s=[],i,a=t===2?"<svg>":t===3?"<math>":"",o=N;for(let d=0;d<e;d++){let n=r[d],p,m,h=-1,_=0;for(;_<n.length&&(o.lastIndex=_,m=o.exec(n),m!==null);)_=o.lastIndex,o===N?m[1]==="!--"?o=mt:m[1]!==void 0?o=gt:m[2]!==void 0?(yt.test(m[2])&&(i=RegExp("</"+m[2],"g")),o=x):m[3]!==void 0&&(o=x):o===x?m[0]===">"?(o=i??N,h=-1):m[1]===void 0?h=-2:(h=o.lastIndex-m[2].length,p=m[1],o=m[3]===void 0?x:m[3]==='"'?ft:_t):o===ft||o===_t?o=x:o===mt||o===gt?o=N:(o=x,i=void 0);let f=o===x&&r[d+1].startsWith("/>")?" ":"";a+=o===N?n+It:h>=0?(s.push(p),n.slice(0,h)+$t+n.slice(h)+b+f):n+b+(h===-2?d:f)}return[xt(r,a+(r[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),s]},L=class r{constructor({strings:t,_$litType$:e},s){let i;this.parts=[];let a=0,o=0,d=t.length-1,n=this.parts,[p,m]=Bt(t,e);if(this.el=r.createElement(p,s),w.currentNode=this.el.content,e===2||e===3){let h=this.el.content.firstChild;h.replaceWith(...h.childNodes)}for(;(i=w.nextNode())!==null&&n.length<d;){if(i.nodeType===1){if(i.hasAttributes())for(let h of i.getAttributeNames())if(h.endsWith($t)){let _=m[o++],f=i.getAttribute(h).split(b),g=/([.?@])?(.*)/.exec(_);n.push({type:1,index:a,name:g[2],strings:f,ctor:g[1]==="."?Y:g[1]==="?"?G:g[1]==="@"?J:E}),i.removeAttribute(h)}else h.startsWith(b)&&(n.push({type:6,index:a}),i.removeAttribute(h));if(yt.test(i.tagName)){let h=i.textContent.split(b),_=h.length-1;if(_>0){i.textContent=I?I.emptyScript:"";for(let f=0;f<_;f++)i.append(h[f],D()),w.nextNode(),n.push({type:2,index:++a});i.append(h[_],D())}}}else if(i.nodeType===8)if(i.data===bt)n.push({type:2,index:a});else{let h=-1;for(;(h=i.data.indexOf(b,h+1))!==-1;)n.push({type:7,index:a}),h+=b.length-1}a++}}static createElement(t,e){let s=A.createElement("template");return s.innerHTML=t,s}};function k(r,t,e=r,s){if(t===S)return t;let i=s!==void 0?e._$Co?.[s]:e._$Cl,a=T(t)?void 0:t._$litDirective$;return i?.constructor!==a&&(i?._$AO?.(!1),a===void 0?i=void 0:(i=new a(r),i._$AT(r,e,s)),s!==void 0?(e._$Co??=[])[s]=i:e._$Cl=i),i!==void 0&&(t=k(r,i._$AS(r,t.values),i,s)),t}var K=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:s}=this._$AD,i=(t?.creationScope??A).importNode(e,!0);w.currentNode=i;let a=w.nextNode(),o=0,d=0,n=s[0];for(;n!==void 0;){if(o===n.index){let p;n.type===2?p=new O(a,a.nextSibling,this,t):n.type===1?p=new n.ctor(a,n.name,n.strings,this,t):n.type===6&&(p=new Z(a,this,t)),this._$AV.push(p),n=s[++d]}o!==n?.index&&(a=w.nextNode(),o++)}return w.currentNode=A,i}p(t){let e=0;for(let s of this._$AV)s!==void 0&&(s.strings!==void 0?(s._$AI(t,s,e),e+=s.strings.length-2):s._$AI(t[e])),e++}},O=class r{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,s,i){this.type=2,this._$AH=c,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=s,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=k(this,t,e),T(t)?t===c||t==null||t===""?(this._$AH!==c&&this._$AR(),this._$AH=c):t!==this._$AH&&t!==S&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):Vt(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==c&&T(this._$AH)?this._$AA.nextSibling.data=t:this.T(A.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:s}=t,i=typeof s=="number"?this._$AC(t):(s.el===void 0&&(s.el=L.createElement(xt(s.h,s.h[0]),this.options)),s);if(this._$AH?._$AD===i)this._$AH.p(e);else{let a=new K(i,this),o=a.u(this.options);a.p(e),this.T(o),this._$AH=a}}_$AC(t){let e=vt.get(t.strings);return e===void 0&&vt.set(t.strings,e=new L(t)),e}k(t){X(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,s,i=0;for(let a of t)i===e.length?e.push(s=new r(this.O(D()),this.O(D()),this,this.options)):s=e[i],s._$AI(a),i++;i<e.length&&(this._$AR(s&&s._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let s=ut(t).nextSibling;ut(t).remove(),t=s}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},E=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,s,i,a){this.type=1,this._$AH=c,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=a,s.length>2||s[0]!==""||s[1]!==""?(this._$AH=Array(s.length-1).fill(new String),this.strings=s):this._$AH=c}_$AI(t,e=this,s,i){let a=this.strings,o=!1;if(a===void 0)t=k(this,t,e,0),o=!T(t)||t!==this._$AH&&t!==S,o&&(this._$AH=t);else{let d=t,n,p;for(t=a[0],n=0;n<a.length-1;n++)p=k(this,d[s+n],e,n),p===S&&(p=this._$AH[n]),o||=!T(p)||p!==this._$AH[n],p===c?t=c:t!==c&&(t+=(p??"")+a[n+1]),this._$AH[n]=p}o&&!i&&this.j(t)}j(t){t===c?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},Y=class extends E{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===c?void 0:t}},G=class extends E{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==c)}},J=class extends E{constructor(t,e,s,i,a){super(t,e,s,i,a),this.type=5}_$AI(t,e=this){if((t=k(this,t,e,0)??c)===S)return;let s=this._$AH,i=t===c&&s!==c||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,a=t!==c&&(s===c||i);i&&this.element.removeEventListener(this.name,this,s),a&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},Z=class{constructor(t,e,s){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=s}get _$AU(){return this._$AM._$AU}_$AI(t){k(this,t)}};var jt=Q.litHtmlPolyfillSupport;jt?.(L,O),(Q.litHtmlVersions??=[]).push("3.3.3");var wt=(r,t,e)=>{let s=e?.renderBefore??t,i=s._$litPart$;if(i===void 0){let a=e?.renderBefore??null;s._$litPart$=i=new O(t.insertBefore(D(),a),a,void 0,e??{})}return i._$AI(r),i};var et=globalThis,y=class extends v{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=wt(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return S}};y._$litElement$=!0,y.finalized=!0,et.litElementHydrateSupport?.({LitElement:y});var Wt=et.litElementPolyfillSupport;Wt?.({LitElement:y});(et.litElementVersions??=[]).push("4.2.2");function st(r,t=!1){let e=r.points;if(!e.length)return l`<div class="trend-empty">No readings in the last 14 days</div>`;let s=t?600:160,i=t?150:48,a=e.map(g=>g.v),o=Math.min(...a),d=Math.max(...a)-o||Math.abs(o)*.05||1,n=e.map(g=>new Date(g.t).getTime()),p=n[n.length-1]-n[0]||1,m=g=>6+(n[g]-n[0])/p*(s-12),h=g=>i-8-(g-o)/d*(i-16),_=[],f="";return e.forEach((g,$)=>{$&&g.provider!==e[$-1].provider&&(_.push(f),f=""),f+=`${f?" L":"M"}${m($)},${h(g.v)}`}),_.push(f),l`<svg class="sparkline" viewBox="0 0 ${s} ${i}" role="img" aria-label="Recorded trend over 14 days. Lines break when the source changes.">
    ${_.map(g=>P`<path d=${g}></path>`)}
    ${e.map((g,$)=>P`<circle cx=${m($)} cy=${h(g.v)} r=${t?2.5:1.8}><title>${g.v} ${r.unit} · ${new Date(g.t).toLocaleString()}</title></circle>`)}
  </svg>`}function it(r,t){if(t.state==="source_changed")return"Source changed. Compare with care.";if(t.state==="conflict")return"Sources disagree. Review readings.";if(t.delta===null)return"More history needed for a comparison";let e=r._display(Math.abs(t.delta),t.unit),s=t.unit==="count"?0:1;if(Number(e.value.toFixed(s))===0)return"No visible change at this precision";let i=e.unit==="count"?"steps":e.unit==="%"?"percentage points":e.unit;return`${t.delta>0?"+":t.delta<0?"\u2212":""}${r._fmt(e.value,s)} ${i} \xB7 ${t.state==="steady"?"little change":t.delta>0?"up":"down"}`}function St(r,t){let e=t.current;return e?`${t.stale?"Older reading \xB7 ":"Observed "}${r._when(e.observed_at)}`:"No readings yet"}function At(r,t){return l`<button class="metric-row ${t.stale?"stale":""}" @click=${e=>r._openDetail(t.metric,e)}>
    <div><span class="metric-name">${r._label(t.metric)}</span><span class="metric-source">${t.current?r._providerName(t.current.provider):"Connect a source or log a reading"}</span></div>
    <div class="row-trend">${st(t)}</div>
    <div class="metric-value">${r._metricValue(t.current,t.unit==="count"?0:1)}<span class="metric-source">${St(r,t)}</span></div>
    <div class="row-change">${t.current?it(r,t):"No comparison yet"}${t.delta!==null?l`<span class="metric-source">${t.comparison_label}</span>`:c}</div>
    <span class="row-arrow" aria-hidden="true">›</span>
  </button>`}function kt(r){let t=r._overview;if(!t)return l`<p role="status">${r._loading?"Loading your health record\u2026":"Health data is unavailable."}</p>`;let e=t.metrics.filter(o=>o.current),s=e[0],i=e.filter(o=>o!==s),a=t.metrics.filter(o=>!o.current);return l`
    <div class="overview-actions"><button @click=${()=>r._openForm("measure")}>Log a measurement</button><button @click=${()=>r._openForm("workout")}>Log a workout</button></div>
    ${r._measurementForm()}${r._workoutForm()}
    ${s?l`<section class="lead-change ${s.stale?"stale":""}">
      <div class="lead-copy"><p class="eyebrow">${s.state==="changed"&&!s.stale?"A change in your record":s.state==="conflict"?"Worth a closer look":"Your latest readings"}</p>
        <h2>${r._label(s.metric)}</h2><div class="lead-value">${r._metricValue(s.current,s.unit==="count"?0:1)}</div>
        <p class="change-line">${it(r,s)}</p>
        ${s.delta!==null?l`<p class="sub">${s.comparison_label}</p>`:c}
        <p class="sub">${r._providerName(s.current.provider)} · ${St(r,s)}</p>
        <button class="primary" @click=${o=>r._openDetail(s.metric,o)}>Review ${r._label(s.metric).toLowerCase()}</button>
      </div><div class="lead-chart">${st(s,!0)}<span class="sub">Last 14 days · recorded readings</span></div>
    </section>`:l`<section class="intro-empty"><p class="eyebrow">Start with one reading</p><h2>Your health record starts here.</h2><p>Connect your scale or activity tracker in Health Assistant’s integration settings, or log a measurement above. Your history stays on this Home Assistant instance.</p><a href="/config/integrations/integration/health_assistant">Open integration settings</a></section>`}
    ${i.length?l`<section class="metric-section" aria-label="Health metrics"><div class="section-heading"><h2>The rest of your record</h2><span class="sub">Select a metric for readings and sources</span></div>${i.map(o=>At(r,o))}</section>`:c}
    ${a.length?l`<details class="missing-metrics"><summary>${a.length} ${a.length===1?"metric":"metrics"} without readings</summary><p class="sub">Connect a source, add a reading, or open a metric to restore an excluded record.</p>${a.map(o=>At(r,o))}</details>`:c}
    <section class="workout-section"><div class="section-heading"><h2>This week’s training</h2><span class="sub">${t.workout_count} ${t.workout_count===1?"workout":"workouts"} in the last 7 days</span></div>
      ${t.workouts.length?l`<div class="workout-strip">${t.workouts.map(o=>l`<article class="workout-item"><span class="eyebrow">${r._when(o.started_at)}</span><h3>${o.title}</h3><p>${r._fmt(o.duration_seconds/60,0)} min · ${o.workout_type}</p><span class="sub">${r._providerName(o.provider)}</span></article>`)}</div>`:l`<p class="empty-note">No workouts recorded this week. Connected workout sources and manual entries will appear here.</p>`}
    </section>
    <details class="source-status"><summary>Sources <span>${t.providers.filter(o=>o.degraded).length?"\xB7 needs attention":"\xB7 status"}</span></summary><p class="sub">Successful source operations and measurement times are different. A source can be working while its latest reading is old.</p>${t.providers.map(o=>l`<div class="source-row"><strong>${r._providerName(o.key)}</strong><span>${o.degraded?"Needs attention":o.had_error?"Working again":o.last_success?"Working":"Waiting for data"}</span><span class="sub">${o.last_success?`Last successful operation ${r._when(o.last_success)}`:"No successful operation since reload"}</span></div>`)}<a href="/config/integrations/integration/health_assistant">Manage sources in integration settings</a></details>
  `}function Et(r){if(!r._detailMetric)return c;let t=r._overview?.metrics.find(i=>i.metric===r._detailMetric),e=r._detail,s=e?.observation;return l`<dialog aria-labelledby="detail-title" @cancel=${()=>r._closeDetail()}>
    <div class="detail-header"><div><p class="eyebrow">Readings and sources</p><h2 id="detail-title">${r._label(r._detailMetric)}</h2></div><button autofocus @click=${()=>r._closeDetail()}>Close</button></div>
    ${r._detailError?l`<p class="error" role="alert">${r._detailError}<button @click=${()=>r._loadDetail()}>Try again</button></p>`:c}
    ${t?l`<div class="detail-trend">${st(t,!0)}<p class="sub">${it(r,t)}${t.delta!==null?` \xB7 ${t.comparison_label}`:""}</p></div>`:c}
    ${r._detailLoading?l`<p role="status">Loading readings…</p>`:c}
    ${s?l`<section class="reading-detail"><div class="section-heading"><h3>${s.excluded?"Excluded reading":"Selected reading"}</h3><span class="reading-value">${r._metricValue(s)}</span></div><p>${new Date(s.observed_at).toLocaleString()} · ${r._providerName(s.provider)}</p>
      ${s.possible_duplicate?l`<p class="notice">Nearby sources may disagree. Review the original claims and nearby readings before changing anything.</p>`:c}
      ${s.excluded?l`<p class="notice">Kept in your history, excluded from summaries and trends.</p>`:c}
      <h4>Source claims</h4><p class="sub">The selected claim supplies this record’s value. Source priority resolves equivalent claims; nearby records are shown separately.</p>
      ${e.claims.map(i=>l`<div class="claim-row"><div><strong>${r._providerName(i.provider)}</strong><span class="metric-source">${i.selected?"Selected claim":"Retained claim"} · ${new Date(i.observed_at).toLocaleString()}</span><span class="source-id">${i.external_id}</span></div><span>${r._metricValue(i)}</span></div>`)}
      ${e.claim_count>e.claims.length?l`<p class="sub">Showing ${e.claims.length} of ${e.claim_count} claims.</p>`:c}
      ${e.nearby.length?l`<h4>Nearby readings</h4>${e.nearby.map(i=>l`<button class="record-button" ?disabled=${r._detailLoading} @click=${()=>r._loadDetail(i.id)}><span>${r._providerName(i.provider)} · ${r._when(i.observed_at)}</span><span>${r._metricValue(i)}</span></button>`)}`:c}
      ${r.hass.user?.is_admin?l`<div class="exclusion-control"><p class="sub">${s.excluded?"Restore this reading to summaries and trends.":"An incorrect reading can be excluded without deleting its source history. You can restore it later."}</p><button ?disabled=${!!r._busyId||r._detailLoading} @click=${()=>r._toggleExclusion()}>${r._busyId?"Saving\u2026":s.excluded?"Restore reading":"Exclude reading"}</button></div>`:l`<p class="sub">An administrator can exclude or restore incorrect readings.</p>`}
    </section>`:r._detailLoading?c:l`<p>No ${r._showExcluded?"excluded ":""}readings to show.</p>`}
    <section class="record-history"><div class="section-heading"><h3>Browse readings</h3><label class="excluded-toggle"><input type="checkbox" .checked=${r._showExcluded} @change=${i=>{r._showExcluded=i.target.checked,r._detail=void 0,r._loadDetail()}} /> Excluded only</label></div><p class="sub">Most recently added first</p>
    ${r._records.map(i=>l`<button class="record-button ${s?.id===i.id?"selected":""}" ?disabled=${r._detailLoading} @click=${()=>r._loadDetail(i.id)}><span>${new Date(i.observed_at).toLocaleString()}<span class="metric-source">${r._providerName(i.provider)}</span></span><span>${r._metricValue(i)}</span></button>`)}
    ${r._nextRecord?l`<button ?disabled=${r._detailLoading} @click=${()=>r._loadDetail(s?.id,!0)}>Load older readings</button>`:c}</section>
  </dialog>`}var Ct=M`
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
`;var Ft=2.204622621848776,Kt=1/1609.344,V=[{key:"weight",label:"Weight"},{key:"body_fat_percentage",label:"Body fat"},{key:"lean_mass",label:"Lean mass"},{key:"steps",label:"Steps"},{key:"distance",label:"Distance"},{key:"active_energy",label:"Active energy"}],Yt=[7,30,90],rt={ha_entity:"Home Assistant sensors",manual:"Manual entries",withings:"Withings",fitbit:"Fitbit",hevy:"Hevy"},ot=class extends y{static properties={hass:{attribute:!1},narrow:{type:Boolean},panel:{attribute:!1},_overview:{state:!0},_loading:{state:!0},_detailMetric:{state:!0},_detail:{state:!0},_records:{state:!0},_showExcluded:{state:!0},_detailError:{state:!0},_detailLoading:{state:!0},_busyId:{state:!0},_series:{state:!0},_tab:{state:!0},_metric:{state:!0},_days:{state:!0},_error:{state:!0},_form:{state:!0},_saving:{state:!0}};constructor(){super(),this._tab="overview",this._metric="weight",this._days=30,this._form=null,this._saving=!1,this._loadedOnce=!1,this._showExcluded=!1,this._records=[],this._request=0,this._detailRequest=0}get _domain(){return this.panel&&this.panel.config&&this.panel.config.domain||"health_assistant"}get _imperial(){return!!(this.hass&&this.hass.config&&this.hass.config.unit_system&&this.hass.config.unit_system.length==="mi")}updated(t){t.has("hass")&&this.hass&&!this._loadedOnce&&(this._loadedOnce=!0,this._refresh())}connectedCallback(){super.connectedCallback(),this._timer=window.setInterval(()=>{this.hass&&!this._loading&&this._refresh()},6e4)}disconnectedCallback(){super.disconnectedCallback(),window.clearInterval(this._timer)}async _refresh(){let t=++this._request;this._loading=!0,this._error=void 0;try{let e=await this.hass.callWS({type:`${this._domain}/overview`});t===this._request&&(this._overview=e),this._tab==="trends"&&await this._loadSeries()}catch{t===this._request&&(this._error="Health data could not refresh. Check the integration and try again.")}finally{t===this._request&&(this._loading=!1)}}_providerName(t){return rt[t]||this._overview?.providers.find(e=>e.key===t)?.name||t.replaceAll("_"," ")}_label(t){return V.find(e=>e.key===t)?.label||t}async _openDetail(t,e){this._opener=e?.currentTarget,this._detailMetric=t,this._detail=void 0,this._showExcluded=!1,this._records=[],await this.updateComplete,this.shadowRoot.querySelector("dialog").showModal(),await this._loadDetail()}_closeDetail(){this._detailRequest++,this.shadowRoot.querySelector("dialog")?.close(),this._detailMetric=void 0,this._opener?.focus()}async _loadDetail(t,e=!1){let s=++this._detailRequest,i=this._detailMetric;if(!i)return;this._detailLoading=!0,this._detailError=void 0;let a=this._overview?.metrics.find(o=>o.metric===i)?.current;try{let o=await this.hass.callWS({type:`${this._domain}/observations`,metric:i,excluded:this._showExcluded,limit:20,...e&&this._nextRecord?{before_id:this._nextRecord}:{}}),d=t||(this._showExcluded?o.observations[0]?.id:a?.id),n=d?await this.hass.callWS({type:`${this._domain}/observation_detail`,observation_id:d}):void 0;if(s!==this._detailRequest)return;this._records=e?[...this._records,...o.observations]:o.observations,this._nextRecord=o.next_before_id,this._detail=n}catch{s===this._detailRequest&&(this._detailError="That reading could not load. It may have changed during a sync. Try again.")}finally{s===this._detailRequest&&(this._detailLoading=!1)}}async _toggleExclusion(){let t=this._detail?.observation;if(!(!t||this._busyId)){this._busyId=t.id,this._detailError=void 0;try{await this.hass.callWS({type:`${this._domain}/observation_exclusion`,observation_id:t.id,excluded:!t.excluded}),await this._refresh(),await this._loadDetail(t.id)}catch{this._detailError="The reading could not be changed. Refresh and try again."}finally{this._busyId=void 0,await this.updateComplete,this.shadowRoot.querySelector(".exclusion-control button")?.focus()}}}async _loadSeries(){let t=(this._seriesRequest||0)+1;this._seriesRequest=t,this._series=void 0;try{let e=await this.hass.callWS({type:`${this._domain}/time_series`,metric:this._metric,days:this._days});t===this._seriesRequest&&(this._series=e)}catch{t===this._seriesRequest&&(this._error="Trend data could not load. Try refreshing.")}}_setTab(t){this._tab=t,t==="trends"?this._loadSeries():this._refresh()}_setMetric(t){this._metric=t,this._loadSeries()}_setDays(t){this._days=t,this._loadSeries()}_display(t,e){return t==null?null:e==="kg"&&this._imperial?{value:t*Ft,unit:"lb"}:e==="m"&&this._imperial?{value:t*Kt,unit:"mi"}:e==="m"&&t>=1e3?{value:t/1e3,unit:"km"}:{value:t,unit:e}}_fmt(t,e=1){return new Intl.NumberFormat(void 0,{maximumFractionDigits:e}).format(t)}_when(t){let e=new Date(t),i=Math.floor((new Date-e)/864e5);return i<=0?e.toLocaleTimeString(void 0,{hour:"numeric",minute:"2-digit"}):i===1?"yesterday":i<7?`${i} days ago`:e.toLocaleDateString()}_metricValue(t,e=1){if(!t)return l`<span class="empty-value">no data</span>`;let s=this._display(t.value,t.unit),i=s.unit==="count"?c:l`<span class="unit">${s.unit}</span>`;return l`<span class="value">${this._fmt(s.value,e)}</span>${i}`}_defaultUnit(t){return t==="weight"||t==="lean_mass"?this._imperial?"lb":"kg":t==="distance"?this._imperial?"mi":"km":t==="body_fat_percentage"?"%":t==="active_energy"?"kcal":""}_localNow(t=0){let e=new Date(Date.now()-t*6e4),s=i=>String(i).padStart(2,"0");return`${e.getFullYear()}-${s(e.getMonth()+1)}-${s(e.getDate())}T${s(e.getHours())}:${s(e.getMinutes())}`}_openForm(t){this._error=void 0,this._form=this._form===t?null:t}_formValue(t){let e=this.shadowRoot.getElementById(t);return e?e.value.trim():""}async _submitMeasurement(t){t.preventDefault();let e=Number(this._formValue("m-value"));if(!Number.isFinite(e)){this._error="Enter a numeric value";return}let i={metric:this._formValue("m-metric"),value:e},a=this._formValue("m-unit");a&&a!=="count"&&(i.unit=a);let o=this._formValue("m-when");o&&(i.observed_at=new Date(o).toISOString()),await this._callAction("add_observation",i)}async _submitWorkout(t){t.preventDefault();let e=this._formValue("w-type"),s=this._formValue("w-start"),i=this._formValue("w-end");if(!e||!s||!i){this._error="Workout type, start, and end are required";return}let a={workout_type:e,start:new Date(s).toISOString(),end:new Date(i).toISOString()},o=this._formValue("w-title");o&&(a.title=o);let d=this._formValue("w-energy");d&&(a.energy_kcal=Number(d));let n=this._formValue("w-distance");n&&(a.distance=Number(n),a.distance_unit=this._imperial?"mi":"km"),await this._callAction("add_workout",a)}async _callAction(t,e){this._saving=!0,this._error=void 0;try{await this.hass.callService(this._domain,t,e),this._form=null,await this._refresh()}catch(s){this._error=s&&s.message||"Unable to save"}finally{this._saving=!1}}_measurementForm(){return this._form!=="measure"?c:l`
      <form class="entry" @submit=${this._submitMeasurement}>
        <label>Metric
          <select id="m-metric" @change=${t=>{let e=this.shadowRoot.getElementById("m-unit");e&&(e.value=this._defaultUnit(t.target.value))}}>
            ${V.map(t=>l`<option value=${t.key}>${t.label}</option>`)}
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
    `}_workoutForm(){return this._form!=="workout"?c:l`
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
    `}_renderOverview(){return kt(this)}_chart(){let t=this._series;if(!t)return l`<p role="status">Loading trend…</p>`;if(t.points.length===0)return l`<p class="empty-value">
        No ${this._metricLabel().toLowerCase()} data in the last ${this._days} days.
      </p>`;let e=640,s=260,i={left:54,right:16,top:16,bottom:34},a=t.points.map(u=>({time:new Date(u.t).getTime(),shown:this._display(u.v,t.unit),provider:u.provider})),o=a[0].shown.unit,d=a.map(u=>u.shown.value),n=a.map(u=>u.time),p=Math.min(...d),m=Math.max(...d),h=m-p||Math.abs(m)*.1||1,_=Math.min(...n),f=Math.max(...n),g=f-_||1,$=u=>i.left+(u-_)/g*(e-i.left-i.right),z=u=>s-i.bottom-(u-(p-h*.05))/(h*1.1)*(s-i.top-i.bottom),Mt=a.map((u,Dt)=>`${Dt===0?"M":"L"}${$(u.time).toFixed(1)},${z(u.shown.value).toFixed(1)}`).join(" "),Rt=a.length<=120?a.map(u=>P`<circle cx="${$(u.time)}" cy="${z(u.shown.value)}" r="3">
                <title>${this._fmt(u.shown.value)} ${o} · ${new Date(u.time).toLocaleString()} · ${rt[u.provider]||u.provider}</title>
              </circle>`):c,Nt=[...new Set(t.points.map(u=>u.provider))].map(u=>rt[u]||u);return l`
      <svg viewBox="0 0 ${e} ${s}" role="img">
        <line class="axis" x1="${i.left}" y1="${s-i.bottom}" x2="${e-i.right}" y2="${s-i.bottom}"></line>
        <line class="axis" x1="${i.left}" y1="${i.top}" x2="${i.left}" y2="${s-i.bottom}"></line>
        <text class="tick" x="${i.left-8}" y="${z(m)+4}" text-anchor="end">${this._fmt(m)}</text>
        <text class="tick" x="${i.left-8}" y="${z(p)+4}" text-anchor="end">${this._fmt(p)}</text>
        <text class="tick" x="${i.left}" y="${s-10}">${new Date(_).toLocaleDateString()}</text>
        <text class="tick" x="${e-i.right}" y="${s-10}" text-anchor="end">${new Date(f).toLocaleDateString()}</text>
        <path class="line" d="${Mt}"></path>
        ${Rt}
      </svg>
      <div class="sub caption">
        ${t.points.length} points${o==="count"?"":` (${o})`}
        ${t.downsampled?" \xB7 downsampled":""} · from ${Nt.join(", ")}
      </div>
    `}_metricLabel(){let t=V.find(e=>e.key===this._metric);return t?t.label:this._metric}_renderTrends(){return l`
      <div class="card wide">
        <div class="selector">
          ${V.map(t=>l`<button
              class=${this._metric===t.key?"active":""}
              @click=${()=>this._setMetric(t.key)}
            >
              ${t.label}
            </button>`)}
        </div>
        <div class="selector">
          ${Yt.map(t=>l`<button
              class=${this._days===t?"active":""}
              @click=${()=>this._setDays(t)}
            >
              ${t} days
            </button>`)}
        </div>
        ${this._chart()}
      </div>
    `}render(){return l`
      <div class="wrapper">
        <header>
          <div class="header-identity">${this.narrow?l`<button aria-label="Open sidebar" @click=${()=>this.dispatchEvent(new window.Event("hass-toggle-menu",{bubbles:!0,composed:!0}))}>Menu</button>`:c}<div><h1>Health</h1><p class="page-subtitle">Your record, at a glance</p></div></div>
          <nav aria-label="Health views">
            <button @click=${this._refresh} ?disabled=${this._loading}>${this._loading?"Refreshing":"Refresh"}</button>
            <button
              class=${this._tab==="overview"?"active":""}
              @click=${()=>this._setTab("overview")}
            >
              Overview
            </button>
            <button
              class=${this._tab==="trends"?"active":""}
              @click=${()=>this._setTab("trends")}
            >
              Trends
            </button>
          </nav>
        </header>
        ${this._error?l`<div class="card error">${this._error}</div>`:c}
        ${this._tab==="overview"?this._renderOverview():this._renderTrends()}
        ${Et(this)}
      </div>
    `}static styles=[Ct,M`
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
  `]};customElements.get("health-assistant-panel")||customElements.define("health-assistant-panel",ot);
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
