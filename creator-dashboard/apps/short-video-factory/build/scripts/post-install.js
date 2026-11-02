const { execFileSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const packageDir = path.dirname(require.resolve('ffmpeg-static/package.json'))
const ffmpeg = require('ffmpeg-static')

if (!fs.existsSync(ffmpeg)) {
  console.log('Downloading ffmpeg...')
  execFileSync(process.execPath, [path.join(packageDir, 'install.js')], {
    cwd: packageDir,
    env: {
      ...process.env,
      FFMPEG_BINARIES_URL:
        process.env.FFMPEG_BINARIES_URL ||
        process.env.npm_config_ffmpeg_binaries_url ||
        'https://cdn.npmmirror.com/binaries/ffmpeg-static',
    },
    stdio: 'inherit',
  })
}

if (!fs.existsSync(ffmpeg)) {
  throw new Error(`FFmpeg download did not create ${ffmpeg}`)
}

console.log(`FFmpeg available at: ${ffmpeg}`)
if (process.platform !== 'win32') {
  fs.chmodSync(ffmpeg, 0o755)
}
