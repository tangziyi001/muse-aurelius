import os, sys
sys.path.insert(0, "/config/etsy-browser")
from cdp import launch, nap, wait_for_js
import json

JS = """(() => {
  function collect(root, acc) {
    acc = acc || [];
    root.querySelectorAll('input').forEach(el => acc.push(el));
    root.querySelectorAll('*').forEach(el => { if (el.shadowRoot) collect(el.shadowRoot, acc); });
    return acc;
  }
  const inputs = collect(document);
  const html = document.body.innerHTML.slice(0, 2000);
  return {count: inputs.length,
    inputs: inputs.map(el => ({type: el.type, name: el.name, id: el.id, cls: (el.className||'').toString().slice(0,60), vis: !!(el.offsetParent)})),
    hasEmailLabel: /Email address/.test(document.body.innerText),
    shadowHosts: document.querySelectorAll('*').length,
    htmlHead: html};
})()"""

cdp, proc = launch(headed=True)
try:
    cdp.navigate("https://www.etsy.com/signin")
    nap(3, 5)
    wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
    nap(3, 4)
    print(json.dumps(cdp.evaluate(JS), indent=1)[:3000])
finally:
    cdp.close()
