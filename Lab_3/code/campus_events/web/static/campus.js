"use strict";

document.addEventListener("submit", (event) => {
  const message = event.target.dataset.confirm;
  if (message && !window.confirm(message)) event.preventDefault();
});

const editor = document.querySelector("[data-editor]");
if (editor) {
  const currentKeys = [...editor.querySelectorAll('[name="session_key"]')]
    .map((input) => Number(input.value));
  let nextKey = Math.max(0, ...currentKeys) + 1;

  function cloneForSession(selector, key) {
    const fragment = editor.querySelector(selector).content.cloneNode(true);
    for (const control of fragment.querySelectorAll("[name]")) {
      control.name = control.name.replace("__KEY__", key);
      if (control.name === "session_key") control.value = key;
    }
    return fragment;
  }

  editor.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    const slot = button.closest("[data-session]");
    if (button.hasAttribute("data-add-session")) {
      const container = editor.querySelector("[data-sessions]");
      container.append(cloneForSession("[data-session-template]", String(nextKey++)));
      container.lastElementChild.querySelector('input:not([type="hidden"])').focus();
    } else if (button.hasAttribute("data-add-category") && slot) {
      const key = slot.querySelector('[name="session_key"]').value;
      const container = slot.querySelector("[data-categories]");
      container.append(cloneForSession("[data-category-template]", key));
      container.lastElementChild.querySelector("input").focus();
    } else if (button.hasAttribute("data-remove-category")) {
      button.closest("[data-category]").remove();
      slot.querySelector("[data-add-category]").focus();
    } else if (button.hasAttribute("data-remove-session") && slot) {
      slot.remove();
      editor.querySelector("[data-add-session]").focus();
    }
  });
}
