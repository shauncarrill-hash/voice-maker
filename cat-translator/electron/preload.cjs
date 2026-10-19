const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('catApp', {
  copy: (text) => ipcRenderer.invoke('copy', text),
})
