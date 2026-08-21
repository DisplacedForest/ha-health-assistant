var H=globalThis,R=H.ShadowRoot&&(H.ShadyCSS===void 0||H.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,z=Symbol(),st=new WeakMap,C=class{constructor(t,e,s){if(this._$cssResult$=!0,s!==z)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(R&&t===void 0){let s=e!==void 0&&e.length===1;s&&(t=st.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),s&&st.set(e,t))}return t}toString(){return this.cssText}},it=r=>new C(typeof r=="string"?r:r+"",void 0,z),B=(r,...t)=>{let e=r.length===1?r[0]:t.reduce((s,i,o)=>s+(n=>{if(n._$cssResult$===!0)return n.cssText;if(typeof n=="number")return n;throw Error("Value passed to 'css' function must be a 'css' function result: "+n+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+r[o+1],r[0]);return new C(e,r,z)},rt=(r,t)=>{if(R)r.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let s=document.createElement("style"),i=H.litNonce;i!==void 0&&s.setAttribute("nonce",i),s.textContent=e.cssText,r.appendChild(s)}},j=R?r=>r:r=>r instanceof CSSStyleSheet?(t=>{let e="";for(let s of t.cssRules)e+=s.cssText;return it(e)})(r):r;var{is:St,defineProperty:Et,getOwnPropertyDescriptor:Ct,getOwnPropertyNames:kt,getOwnPropertySymbols:Mt,getPrototypeOf:Pt}=Object,L=globalThis,ot=L.trustedTypes,Tt=ot?ot.emptyScript:"",Ot=L.reactiveElementPolyfillSupport,k=(r,t)=>r,I={toAttribute(r,t){switch(t){case Boolean:r=r?Tt:null;break;case Object:case Array:r=r==null?r:JSON.stringify(r)}return r},fromAttribute(r,t){let e=r;switch(t){case Boolean:e=r!==null;break;case Number:e=r===null?null:Number(r);break;case Object:case Array:try{e=JSON.parse(r)}catch{e=null}}return e}},at=(r,t)=>!St(r,t),nt={attribute:!0,type:String,converter:I,reflect:!1,useDefault:!1,hasChanged:at};Symbol.metadata??=Symbol("metadata"),L.litPropertyMetadata??=new WeakMap;var f=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=nt){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let s=Symbol(),i=this.getPropertyDescriptor(t,s,e);i!==void 0&&Et(this.prototype,t,i)}}static getPropertyDescriptor(t,e,s){let{get:i,set:o}=Ct(this.prototype,t)??{get(){return this[e]},set(n){this[e]=n}};return{get:i,set(n){let p=i?.call(this);o?.call(this,n),this.requestUpdate(t,p,s)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??nt}static _$Ei(){if(this.hasOwnProperty(k("elementProperties")))return;let t=Pt(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(k("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(k("properties"))){let e=this.properties,s=[...kt(e),...Mt(e)];for(let i of s)this.createProperty(i,e[i])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[s,i]of e)this.elementProperties.set(s,i)}this._$Eh=new Map;for(let[e,s]of this.elementProperties){let i=this._$Eu(e,s);i!==void 0&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let s=new Set(t.flat(1/0).reverse());for(let i of s)e.unshift(j(i))}else t!==void 0&&e.push(j(t));return e}static _$Eu(t,e){let s=e.attribute;return s===!1?void 0:typeof s=="string"?s:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let s of e.keys())this.hasOwnProperty(s)&&(t.set(s,this[s]),delete this[s]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return rt(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,s){this._$AK(t,s)}_$ET(t,e){let s=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,s);if(i!==void 0&&s.reflect===!0){let o=(s.converter?.toAttribute!==void 0?s.converter:I).toAttribute(e,s.type);this._$Em=t,o==null?this.removeAttribute(i):this.setAttribute(i,o),this._$Em=null}}_$AK(t,e){let s=this.constructor,i=s._$Eh.get(t);if(i!==void 0&&this._$Em!==i){let o=s.getPropertyOptions(i),n=typeof o.converter=="function"?{fromAttribute:o.converter}:o.converter?.fromAttribute!==void 0?o.converter:I;this._$Em=i;let p=n.fromAttribute(e,o.type);this[i]=p??this._$Ej?.get(i)??p,this._$Em=null}}requestUpdate(t,e,s,i=!1,o){if(t!==void 0){let n=this.constructor;if(i===!1&&(o=this[t]),s??=n.getPropertyOptions(t),!((s.hasChanged??at)(o,e)||s.useDefault&&s.reflect&&o===this._$Ej?.get(t)&&!this.hasAttribute(n._$Eu(t,s))))return;this.C(t,e,s)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:s,reflect:i,wrapped:o},n){s&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,n??e??this[t]),o!==!0||n!==void 0)||(this._$AL.has(t)||(this.hasUpdated||s||(e=void 0),this._$AL.set(t,e)),i===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[i,o]of this._$Ep)this[i]=o;this._$Ep=void 0}let s=this.constructor.elementProperties;if(s.size>0)for(let[i,o]of s){let{wrapped:n}=o,p=this[i];n!==!0||this._$AL.has(i)||p===void 0||this.C(i,void 0,o,p)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(s=>s.hostUpdate?.()),this.update(e)):this._$EM()}catch(s){throw t=!1,this._$EM(),s}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};f.elementStyles=[],f.shadowRootOptions={mode:"open"},f[k("elementProperties")]=new Map,f[k("finalized")]=new Map,Ot?.({ReactiveElement:f}),(L.reactiveElementVersions??=[]).push("2.1.2");var J=globalThis,ht=r=>r,D=J.trustedTypes,lt=D?D.createPolicy("lit-html",{createHTML:r=>r}):void 0,mt="$lit$",v=`lit$${Math.random().toFixed(9).slice(2)}$`,$t="?"+v,Ut=`<${$t}>`,A=document,P=()=>A.createComment(""),T=r=>r===null||typeof r!="object"&&typeof r!="function",Z=Array.isArray,Nt=r=>Z(r)||typeof r?.[Symbol.iterator]=="function",V=`[ 	
\f\r]`,M=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,ct=/-->/g,dt=/>/g,g=RegExp(`>|${V}(?:([^\\s"'>=/]+)(${V}*=${V}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),pt=/'/g,ut=/"/g,ft=/^(?:script|style|textarea|title)$/i,Q=r=>(t,...e)=>({_$litType$:r,strings:t,values:e}),_=Q(1),vt=Q(2),qt=Q(3),w=Symbol.for("lit-noChange"),d=Symbol.for("lit-nothing"),_t=new WeakMap,b=A.createTreeWalker(A,129);function yt(r,t){if(!Z(r)||!r.hasOwnProperty("raw"))throw Error("invalid template strings array");return lt!==void 0?lt.createHTML(t):t}var Ht=(r,t)=>{let e=r.length-1,s=[],i,o=t===2?"<svg>":t===3?"<math>":"",n=M;for(let p=0;p<e;p++){let a=r[p],l,u,h=-1,m=0;for(;m<a.length&&(n.lastIndex=m,u=n.exec(a),u!==null);)m=n.lastIndex,n===M?u[1]==="!--"?n=ct:u[1]!==void 0?n=dt:u[2]!==void 0?(ft.test(u[2])&&(i=RegExp("</"+u[2],"g")),n=g):u[3]!==void 0&&(n=g):n===g?u[0]===">"?(n=i??M,h=-1):u[1]===void 0?h=-2:(h=n.lastIndex-u[2].length,l=u[1],n=u[3]===void 0?g:u[3]==='"'?ut:pt):n===ut||n===pt?n=g:n===ct||n===dt?n=M:(n=g,i=void 0);let $=n===g&&r[p+1].startsWith("/>")?" ":"";o+=n===M?a+Ut:h>=0?(s.push(l),a.slice(0,h)+mt+a.slice(h)+v+$):a+v+(h===-2?p:$)}return[yt(r,o+(r[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),s]},O=class r{constructor({strings:t,_$litType$:e},s){let i;this.parts=[];let o=0,n=0,p=t.length-1,a=this.parts,[l,u]=Ht(t,e);if(this.el=r.createElement(l,s),b.currentNode=this.el.content,e===2||e===3){let h=this.el.content.firstChild;h.replaceWith(...h.childNodes)}for(;(i=b.nextNode())!==null&&a.length<p;){if(i.nodeType===1){if(i.hasAttributes())for(let h of i.getAttributeNames())if(h.endsWith(mt)){let m=u[n++],$=i.getAttribute(h).split(v),x=/([.?@])?(.*)/.exec(m);a.push({type:1,index:o,name:x[2],strings:$,ctor:x[1]==="."?q:x[1]==="?"?F:x[1]==="@"?K:E}),i.removeAttribute(h)}else h.startsWith(v)&&(a.push({type:6,index:o}),i.removeAttribute(h));if(ft.test(i.tagName)){let h=i.textContent.split(v),m=h.length-1;if(m>0){i.textContent=D?D.emptyScript:"";for(let $=0;$<m;$++)i.append(h[$],P()),b.nextNode(),a.push({type:2,index:++o});i.append(h[m],P())}}}else if(i.nodeType===8)if(i.data===$t)a.push({type:2,index:o});else{let h=-1;for(;(h=i.data.indexOf(v,h+1))!==-1;)a.push({type:7,index:o}),h+=v.length-1}o++}}static createElement(t,e){let s=A.createElement("template");return s.innerHTML=t,s}};function S(r,t,e=r,s){if(t===w)return t;let i=s!==void 0?e._$Co?.[s]:e._$Cl,o=T(t)?void 0:t._$litDirective$;return i?.constructor!==o&&(i?._$AO?.(!1),o===void 0?i=void 0:(i=new o(r),i._$AT(r,e,s)),s!==void 0?(e._$Co??=[])[s]=i:e._$Cl=i),i!==void 0&&(t=S(r,i._$AS(r,t.values),i,s)),t}var W=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:s}=this._$AD,i=(t?.creationScope??A).importNode(e,!0);b.currentNode=i;let o=b.nextNode(),n=0,p=0,a=s[0];for(;a!==void 0;){if(n===a.index){let l;a.type===2?l=new U(o,o.nextSibling,this,t):a.type===1?l=new a.ctor(o,a.name,a.strings,this,t):a.type===6&&(l=new G(o,this,t)),this._$AV.push(l),a=s[++p]}n!==a?.index&&(o=b.nextNode(),n++)}return b.currentNode=A,i}p(t){let e=0;for(let s of this._$AV)s!==void 0&&(s.strings!==void 0?(s._$AI(t,s,e),e+=s.strings.length-2):s._$AI(t[e])),e++}},U=class r{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,s,i){this.type=2,this._$AH=d,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=s,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=S(this,t,e),T(t)?t===d||t==null||t===""?(this._$AH!==d&&this._$AR(),this._$AH=d):t!==this._$AH&&t!==w&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):Nt(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==d&&T(this._$AH)?this._$AA.nextSibling.data=t:this.T(A.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:s}=t,i=typeof s=="number"?this._$AC(t):(s.el===void 0&&(s.el=O.createElement(yt(s.h,s.h[0]),this.options)),s);if(this._$AH?._$AD===i)this._$AH.p(e);else{let o=new W(i,this),n=o.u(this.options);o.p(e),this.T(n),this._$AH=o}}_$AC(t){let e=_t.get(t.strings);return e===void 0&&_t.set(t.strings,e=new O(t)),e}k(t){Z(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,s,i=0;for(let o of t)i===e.length?e.push(s=new r(this.O(P()),this.O(P()),this,this.options)):s=e[i],s._$AI(o),i++;i<e.length&&(this._$AR(s&&s._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let s=ht(t).nextSibling;ht(t).remove(),t=s}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},E=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,s,i,o){this.type=1,this._$AH=d,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=o,s.length>2||s[0]!==""||s[1]!==""?(this._$AH=Array(s.length-1).fill(new String),this.strings=s):this._$AH=d}_$AI(t,e=this,s,i){let o=this.strings,n=!1;if(o===void 0)t=S(this,t,e,0),n=!T(t)||t!==this._$AH&&t!==w,n&&(this._$AH=t);else{let p=t,a,l;for(t=o[0],a=0;a<o.length-1;a++)l=S(this,p[s+a],e,a),l===w&&(l=this._$AH[a]),n||=!T(l)||l!==this._$AH[a],l===d?t=d:t!==d&&(t+=(l??"")+o[a+1]),this._$AH[a]=l}n&&!i&&this.j(t)}j(t){t===d?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},q=class extends E{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===d?void 0:t}},F=class extends E{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==d)}},K=class extends E{constructor(t,e,s,i,o){super(t,e,s,i,o),this.type=5}_$AI(t,e=this){if((t=S(this,t,e,0)??d)===w)return;let s=this._$AH,i=t===d&&s!==d||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,o=t!==d&&(s===d||i);i&&this.element.removeEventListener(this.name,this,s),o&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},G=class{constructor(t,e,s){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=s}get _$AU(){return this._$AM._$AU}_$AI(t){S(this,t)}};var Rt=J.litHtmlPolyfillSupport;Rt?.(O,U),(J.litHtmlVersions??=[]).push("3.3.3");var gt=(r,t,e)=>{let s=e?.renderBefore??t,i=s._$litPart$;if(i===void 0){let o=e?.renderBefore??null;s._$litPart$=i=new U(t.insertBefore(P(),o),o,void 0,e??{})}return i._$AI(r),i};var X=globalThis,y=class extends f{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=gt(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return w}};y._$litElement$=!0,y.finalized=!0,X.litElementHydrateSupport?.({LitElement:y});var Lt=X.litElementPolyfillSupport;Lt?.({LitElement:y});(X.litElementVersions??=[]).push("4.2.2");var Dt=2.204622621848776,zt=1/1609.344,bt=[{key:"weight",label:"Weight"},{key:"body_fat_percentage",label:"Body fat"},{key:"lean_mass",label:"Lean mass"},{key:"steps",label:"Steps"},{key:"distance",label:"Distance"},{key:"active_energy",label:"Active energy"}],Bt=[7,30,90],Y=class extends y{static properties={hass:{attribute:!1},narrow:{type:Boolean},panel:{attribute:!1},_summary:{state:!0},_series:{state:!0},_tab:{state:!0},_metric:{state:!0},_days:{state:!0},_error:{state:!0}};constructor(){super(),this._tab="overview",this._metric="weight",this._days=30,this._loadedOnce=!1}get _domain(){return this.panel&&this.panel.config&&this.panel.config.domain||"health_assistant"}get _imperial(){return!!(this.hass&&this.hass.config&&this.hass.config.unit_system&&this.hass.config.unit_system.length==="mi")}updated(t){t.has("hass")&&this.hass&&!this._loadedOnce&&(this._loadedOnce=!0,this._refresh())}async _refresh(){this._error=void 0;try{this._summary=await this.hass.callWS({type:`${this._domain}/summary`}),await this._loadSeries()}catch(t){this._error=t&&t.message||"Unable to load health data"}}async _loadSeries(){try{this._series=await this.hass.callWS({type:`${this._domain}/time_series`,metric:this._metric,days:this._days})}catch(t){this._error=t&&t.message||"Unable to load trend data"}}_setTab(t){this._tab=t,t==="trends"?this._loadSeries():this._refresh()}_setMetric(t){this._metric=t,this._loadSeries()}_setDays(t){this._days=t,this._loadSeries()}_display(t,e){return t==null?null:e==="kg"&&this._imperial?{value:t*Dt,unit:"lb"}:e==="m"&&this._imperial?{value:t*zt,unit:"mi"}:e==="m"&&t>=1e3?{value:t/1e3,unit:"km"}:{value:t,unit:e}}_fmt(t,e=1){return new Intl.NumberFormat(void 0,{maximumFractionDigits:e}).format(t)}_when(t){let e=new Date(t),i=Math.floor((new Date-e)/864e5);return i<=0?e.toLocaleTimeString(void 0,{hour:"numeric",minute:"2-digit"}):i===1?"yesterday":i<7?`${i} days ago`:e.toLocaleDateString()}_provenance(t){return t?_`<div class="prov">${t.source} · ${this._when(t.observed_at)}</div>`:d}_metricValue(t,e=1){if(!t)return _`<span class="empty-value">no data</span>`;let s=this._display(t.value,t.unit);return _`<span class="value">${this._fmt(s.value,e)}</span>
      <span class="unit">${s.unit}</span>`}_renderEmptyState(){return _`
      <div class="card guide">
        <h2>No health data yet</h2>
        <p>
          Health Assistant builds a local health record from sources you already
          have. Two ways to get started:
        </p>
        <p>
          <b>Map sensors.</b> Open Settings, then Devices &amp; services, choose
          Health Assistant, and press Configure. Pick the sensors that feed each
          metric, like a smart scale's weight sensor.
        </p>
        <p>
          <b>Add records directly.</b> Call the
          <code>${this._domain}.add_observation</code> or
          <code>${this._domain}.add_workout</code> actions from Developer Tools
          or an automation, including backfill with past timestamps.
        </p>
      </div>
    `}_renderOverview(){let t=this._summary;if(!t)return d;if(!t.current_weight&&!t.current_body_fat&&!t.steps_today&&!t.active_energy_today&&!t.latest_workout)return this._renderEmptyState();let s=t.latest_workout;return _`
      <div class="grid">
        <div class="card">
          <h2>Body</h2>
          <div class="row">
            <span class="label">Weight</span>
            <span>${this._metricValue(t.current_weight)}</span>
          </div>
          ${this._provenance(t.current_weight)}
          <div class="row">
            <span class="label">Body fat</span>
            <span>${this._metricValue(t.current_body_fat)}</span>
          </div>
          ${this._provenance(t.current_body_fat)}
        </div>
        <div class="card">
          <h2>Today</h2>
          <div class="row">
            <span class="label">Steps</span>
            <span>${this._metricValue(t.steps_today,0)}</span>
          </div>
          ${this._provenance(t.steps_today)}
          <div class="row">
            <span class="label">Active energy</span>
            <span>${this._metricValue(t.active_energy_today,0)}</span>
          </div>
          ${this._provenance(t.active_energy_today)}
        </div>
        <div class="card">
          <h2>Latest workout</h2>
          ${s?_`
                <div class="row">
                  <span class="label">${s.title||s.workout_type}</span>
                  <span class="value">${this._fmt(s.duration_seconds/60,0)}
                    <span class="unit">min</span></span>
                </div>
                <div class="prov">
                  ${s.workout_type} · ${this._when(s.started_at)} ·
                  ${s.provider}
                </div>
                <div class="row">
                  <span class="label">Last 7 days</span>
                  <span class="value">${t.workouts_last_7_days??"no data"}</span>
                </div>
              `:_`<p class="empty-value">
                No workouts recorded yet. Use the
                <code>${this._domain}.add_workout</code> action.
              </p>`}
        </div>
      </div>
    `}_chart(){let t=this._series;if(!t||t.points.length===0)return _`<p class="empty-value">
        No ${this._metricLabel().toLowerCase()} data in the last ${this._days} days.
      </p>`;let e=640,s=260,i={left:54,right:16,top:16,bottom:34},o=t.points.map(c=>({time:new Date(c.t).getTime(),shown:this._display(c.v,t.unit),source:c.source,raw:c})),n=o[0].shown.unit,p=o.map(c=>c.shown.value),a=o.map(c=>c.time),l=Math.min(...p),u=Math.max(...p),h=u-l||Math.abs(u)*.1||1,m=Math.min(...a),$=Math.max(...a),x=$-m||1,tt=c=>i.left+(c-m)/x*(e-i.left-i.right),N=c=>s-i.bottom-(c-(l-h*.05))/(h*1.1)*(s-i.top-i.bottom),At=o.map((c,xt)=>`${xt===0?"M":"L"}${tt(c.time).toFixed(1)},${N(c.shown.value).toFixed(1)}`).join(" "),wt=o.length<=120?o.map(c=>vt`<circle cx="${tt(c.time)}" cy="${N(c.shown.value)}" r="3">
                <title>${this._fmt(c.shown.value)} ${n} · ${new Date(c.time).toLocaleString()} · ${c.source}</title>
              </circle>`):d,et=[...new Set(t.points.map(c=>c.provider))];return _`
      <svg viewBox="0 0 ${e} ${s}" role="img">
        <line class="axis" x1="${i.left}" y1="${s-i.bottom}" x2="${e-i.right}" y2="${s-i.bottom}"></line>
        <line class="axis" x1="${i.left}" y1="${i.top}" x2="${i.left}" y2="${s-i.bottom}"></line>
        <text class="tick" x="${i.left-8}" y="${N(u)+4}" text-anchor="end">${this._fmt(u)}</text>
        <text class="tick" x="${i.left-8}" y="${N(l)+4}" text-anchor="end">${this._fmt(l)}</text>
        <text class="tick" x="${i.left}" y="${s-10}">${new Date(m).toLocaleDateString()}</text>
        <text class="tick" x="${e-i.right}" y="${s-10}" text-anchor="end">${new Date($).toLocaleDateString()}</text>
        <path class="line" d="${At}"></path>
        ${wt}
      </svg>
      <div class="prov">
        ${t.points.length} points (${n})
        ${t.downsampled?" \xB7 downsampled":""} · source${et.length>1?"s":""}:
        ${et.join(", ")}
      </div>
    `}_metricLabel(){let t=bt.find(e=>e.key===this._metric);return t?t.label:this._metric}_renderTrends(){return _`
      <div class="card wide">
        <div class="selector">
          ${bt.map(t=>_`<button
              class=${this._metric===t.key?"active":""}
              @click=${()=>this._setMetric(t.key)}
            >
              ${t.label}
            </button>`)}
        </div>
        <div class="selector">
          ${Bt.map(t=>_`<button
              class=${this._days===t?"active":""}
              @click=${()=>this._setDays(t)}
            >
              ${t} days
            </button>`)}
        </div>
        ${this._chart()}
      </div>
    `}render(){return _`
      <div class="wrapper">
        <header>
          <h1>Health</h1>
          <nav>
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
        ${this._error?_`<div class="card error">${this._error}</div>`:d}
        ${this._tab==="overview"?this._renderOverview():this._renderTrends()}
      </div>
    `}static styles=B`
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
    button.active {
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
      border-color: var(--primary-color);
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
    .prov {
      color: var(--secondary-text-color);
      font-size: 0.78em;
      margin-top: 2px;
      text-align: right;
    }
    .empty-value {
      color: var(--secondary-text-color);
    }
    code {
      background: var(--secondary-background-color, rgba(127, 127, 127, 0.2));
      border-radius: 4px;
      padding: 1px 5px;
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
  `};customElements.get("health-assistant-panel")||customElements.define("health-assistant-panel",Y);
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
