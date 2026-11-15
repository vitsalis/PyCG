"use strict";
/*
 * A small fake DOM to run the viewer's page script in node, without a
 * browser. It has only what the page uses; it refuses to parse HTML, so a
 * test fails if the page ever builds markup from text.
 *
 * Usage: const {loadPage} = require("./view_dom.js");
 *        const page = loadPage(html, {hash: "#name"});
 */
const vm = require("vm");

let created = 0;

class Node {
  constructor(document) {
    this.ownerDocument = document;
    this.parentNode = null;
    this.childNodes = [];
  }
  get firstChild() {
    return this.childNodes[0] || null;
  }
  get children() {
    return this.childNodes.filter((child) => child instanceof Element);
  }
  get textContent() {
    return this.childNodes.map((child) => child.textContent).join("");
  }
  set textContent(value) {
    this.replaceChildren();
    if (value !== "") this.appendChild(this.ownerDocument.createTextNode(String(value)));
  }
  appendChild(child) {
    if (!(child instanceof Node)) throw new TypeError("appendChild needs a node");
    if (child.parentNode) child.parentNode.removeChild(child);
    child.parentNode = this;
    this.childNodes.push(child);
    return child;
  }
  append(...children) {
    for (const child of children) {
      this.appendChild(typeof child === "string" ? this.ownerDocument.createTextNode(child) : child);
    }
  }
  insertBefore(child, reference) {
    if (reference === null) return this.appendChild(child);
    if (child.parentNode) child.parentNode.removeChild(child);
    const at = this.childNodes.indexOf(reference);
    if (at < 0) throw new Error("insertBefore: reference is not a child");
    child.parentNode = this;
    this.childNodes.splice(at, 0, child);
    return child;
  }
  removeChild(child) {
    const at = this.childNodes.indexOf(child);
    if (at < 0) throw new Error("removeChild: not a child");
    this.childNodes.splice(at, 1);
    child.parentNode = null;
    return child;
  }
  replaceChildren(...children) {
    for (const child of [...this.childNodes]) this.removeChild(child);
    this.append(...children);
  }
  remove() {
    if (this.parentNode) this.parentNode.removeChild(this);
  }
  contains(node) {
    for (let at = node; at; at = at.parentNode) if (at === this) return true;
    return false;
  }
}

class Text extends Node {
  constructor(document, data) {
    super(document);
    this.data = data;
  }
  get textContent() {
    return this.data;
  }
  set textContent(value) {
    this.data = String(value);
  }
}

class ClassList {
  constructor(element) {
    this.element = element;
  }
  values() {
    return (this.element.getAttribute("class") || "").split(/\s+/).filter(Boolean);
  }
  write(values) {
    this.element.setAttribute("class", values.join(" "));
  }
  contains(name) {
    return this.values().includes(name);
  }
  add(...names) {
    this.write([...new Set([...this.values(), ...names])]);
  }
  remove(...names) {
    this.write(this.values().filter((value) => !names.includes(value)));
  }
  toggle(name, force) {
    const on = force === undefined ? !this.contains(name) : force;
    if (on) this.add(name);
    else this.remove(name);
    return on;
  }
}

class Element extends Node {
  constructor(document, tagName) {
    super(document);
    created += 1;
    this.tagName = tagName.toUpperCase();
    this.attributes = new Map();
    this.listeners = new Map();
    this.classList = new ClassList(this);
    this.style = {};
    this.value = "";
    this.checked = false;
    this.disabled = false;
    this.scrolledIntoView = 0;
  }
  get id() {
    return this.getAttribute("id") || "";
  }
  set id(value) {
    this.setAttribute("id", value);
  }
  get className() {
    return this.getAttribute("class") || "";
  }
  set className(value) {
    this.setAttribute("class", value);
  }
  get hidden() {
    return this.attributes.has("hidden");
  }
  set hidden(value) {
    if (value) this.setAttribute("hidden", "");
    else this.removeAttribute("hidden");
  }
  get type() {
    return this.getAttribute("type") || "";
  }
  set type(value) {
    this.setAttribute("type", value);
  }
  set innerHTML(value) {
    throw new Error("the page set innerHTML");
  }
  set outerHTML(value) {
    throw new Error("the page set outerHTML");
  }
  insertAdjacentHTML() {
    throw new Error("the page called insertAdjacentHTML");
  }
  setAttribute(name, value) {
    this.attributes.set(String(name).toLowerCase(), String(value));
  }
  getAttribute(name) {
    const value = this.attributes.get(String(name).toLowerCase());
    return value === undefined ? null : value;
  }
  hasAttribute(name) {
    return this.attributes.has(String(name).toLowerCase());
  }
  removeAttribute(name) {
    this.attributes.delete(String(name).toLowerCase());
  }
  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(listener);
  }
  removeEventListener(type, listener) {
    const list = this.listeners.get(type) || [];
    const at = list.indexOf(listener);
    if (at >= 0) list.splice(at, 1);
  }
  dispatchEvent(event) {
    event.target = event.target || this;
    for (let at = this; at && !event.stopped; at = at.parentNode || at.host) {
      event.currentTarget = at;
      for (const listener of [...((at.listeners && at.listeners.get(event.type)) || [])]) {
        listener.call(at, event);
      }
    }
    return !event.defaultPrevented;
  }
  focus() {
    this.ownerDocument.activeElement = this;
  }
  blur() {
    if (this.ownerDocument.activeElement === this) this.ownerDocument.activeElement = this.ownerDocument.body;
  }
  select() {}
  click() {
    if (this.disabled) return;
    if (this.tagName === "INPUT" && this.type === "checkbox") {
      this.checked = !this.checked;
      this.dispatchEvent(new Event("click"));
      this.dispatchEvent(new Event("change"));
      return;
    }
    this.dispatchEvent(new Event("click"));
  }
  scrollIntoView() {
    this.scrolledIntoView += 1;
  }
}

class Event {
  constructor(type, init = {}) {
    this.type = type;
    Object.assign(this, init);
    this.defaultPrevented = false;
    this.stopped = false;
    this.target = null;
  }
  preventDefault() {
    this.defaultPrevented = true;
  }
  stopPropagation() {
    this.stopped = true;
  }
}

class Document extends Element {
  constructor() {
    super(null, "#document");
    this.ownerDocument = this;
    this.documentElement = this.createElement("html");
    this.body = this.createElement("body");
    this.documentElement.appendChild(this.body);
    this.appendChild(this.documentElement);
    this.activeElement = this.body;
    this.title = "";
  }
  createElement(tagName) {
    return new Element(this, tagName);
  }
  createTextNode(data) {
    return new Text(this, String(data));
  }
  getElementById(id) {
    return find(this, (node) => node.id === id);
  }
}

function find(root, test) {
  for (const child of root.childNodes) {
    if (!(child instanceof Element)) continue;
    if (test(child)) return child;
    const found = find(child, test);
    if (found) return found;
  }
  return null;
}

function findAll(root, test, out = []) {
  for (const child of root.childNodes) {
    if (!(child instanceof Element)) continue;
    if (test(child)) out.push(child);
    findAll(child, test, out);
  }
  return out;
}

function blocks(html) {
  const out = {};
  const pattern = /<script(?: type="application\/json")? id="([\w-]+)">([\s\S]*?)<\/script>/g;
  for (const match of html.matchAll(pattern)) out[match[1]] = match[2];
  return out;
}

/* Run the page's scripts against a fresh fake document. */
function loadPage(html, options = {}) {
  created = 0;
  const document = new Document();
  const app = document.createElement("div");
  app.id = "app";
  document.body.appendChild(app);
  const scripts = blocks(html);
  const data = document.createElement("script");
  data.id = "pycg-document";
  data.setAttribute("type", "application/json");
  data.appendChild(document.createTextNode(scripts["pycg-document"]));
  document.body.appendChild(data);

  const window = new Element(document, "#window");
  const queue = [];
  const location = {
    _hash: options.hash || "",
    get hash() {
      return this._hash;
    },
    set hash(value) {
      const next = value === "" || value.startsWith("#") ? value : "#" + value;
      if (next === this._hash) return;
      this._hash = next;
      queue.push(() => window.dispatchEvent(new Event("hashchange")));
    },
  };
  const context = vm.createContext({
    document,
    window,
    location,
    console,
    Event,
  });
  window.document = document;
  vm.runInContext(scripts["pycg-logic"], context, {filename: "pycg-logic.js"});
  vm.runInContext(scripts["pycg-ui"], context, {filename: "pycg-ui.js"});

  const page = {
    document,
    window,
    location,
    context,
    created: () => created,
    /* Deliver the hash changes that the page queued, as a browser does. */
    settle() {
      while (queue.length) queue.shift()();
    },
    byId: (id) => document.getElementById(id),
    all: (className, root = document) => findAll(root, (node) => node.classList.contains(className)),
    first(className, root = document) {
      const found = findAll(root, (node) => node.classList.contains(className));
      if (!found.length) throw new Error("no element with class " + className);
      return found[0];
    },
    withText(className, text, root = document) {
      const found = findAll(
        root,
        (node) => node.classList.contains(className) && node.textContent === text
      );
      if (!found.length) throw new Error(`no .${className} with text ${JSON.stringify(text)}`);
      return found[0];
    },
    text: (node) => (node || document).textContent,
    type(input, value) {
      input.value = value;
      input.dispatchEvent(new Event("input"));
    },
    key(target, key, init = {}) {
      return target.dispatchEvent(new Event("keydown", {key, ...init}));
    },
    tags: (root = document) => findAll(root, () => true).map((node) => node.tagName),
  };
  page.settle();
  return page;
}

module.exports = {loadPage, Event};
