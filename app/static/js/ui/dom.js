// A tiny element builder. Text is always inserted as text, never as HTML, so content from
// the server or from an uploaded file's metadata cannot inject markup.

function append(parent, child) {
  if (child == null || child === false) return;
  if (Array.isArray(child)) {
    child.forEach((item) => append(parent, item));
    return;
  }
  parent.append(
    child instanceof Node ? child : document.createTextNode(String(child)),
  );
}

export function h(tag, attrs, ...children) {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs ?? {})) {
    if (value == null || value === false) continue;
    if (name === "class") {
      element.className = value;
    } else if (name.startsWith("on") && typeof value === "function") {
      element.addEventListener(name.slice(2).toLowerCase(), value);
    } else {
      element.setAttribute(name, value === true ? "" : value);
    }
  }
  append(element, children);
  return element;
}
