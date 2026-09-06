import { html } from "lit";

export function renderDialog(panel, title, eyebrow, content) {
  return html`<dialog aria-labelledby="detail-title" @cancel=${() => panel._closeDetail()}>
    <div class="detail-header"><div><p class="eyebrow">${eyebrow}</p><h2 id="detail-title">${title}</h2></div><button autofocus @click=${() => panel._closeDetail()}>Close</button></div>
    ${content}
  </dialog>`;
}
