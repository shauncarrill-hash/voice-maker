const { app, BrowserWindow, Menu, clipboard, ipcMain, shell } = require('electron')
const path = require('node:path')

function createWindow() {
  const win = new BrowserWindow({
    width: 900,
    height: 760,
    minWidth: 520,
    minHeight: 500,
    backgroundColor: '#0a0a0a',
    title: 'Cat Voice Translator',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      sandbox: true,
    },
  })
  // External links open in the normal browser, never inside the app.
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
  win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
}

ipcMain.handle('copy', (_event, text) => clipboard.writeText(String(text)))

// macOS needs an Edit menu for copy and paste shortcuts; elsewhere no menu bar.
Menu.setApplicationMenu(
  process.platform === 'darwin' ? Menu.buildFromTemplate([{ role: 'appMenu' }, { role: 'editMenu' }]) : null,
)
app.whenReady().then(() => {
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
