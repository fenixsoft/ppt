/**
 * 腾讯云 CDN 刷新与预热脚本
 * 在部署后自动刷新 CDN 缓存，并预热关键页面
 *
 * 预热 URL 列表从 WARMUP_URLS_FILE（默认 warmup-urls.txt）读取，
 * 由 workflow 在部署机上按当前文件树生成，避免硬编码页面清单过期；
 * 文件缺失时回退到站点根与 ioc deck 入口。
 */

const DEFAULT_PATHS = [
  '/',       // 站点根
  '/ioc/',   // ioc deck 入口
  '/ioc/index.html'
]

async function refreshCDN() {
  // 验证环境变量
  const secretId = process.env.TENCENT_SECRET_ID
  const secretKey = process.env.TENCENT_SECRET_KEY
  const cdnDomain = process.env.CDN_DOMAIN

  if (!secretId || !secretKey || !cdnDomain) {
    console.log('⚠️  腾讯云 CDN 配置不完整，跳过刷新')
    console.log('需要配置以下 GitHub Secrets:')
    console.log('  - TENCENT_SECRET_ID')
    console.log('  - TENCENT_SECRET_KEY')
    console.log('  - CDN_DOMAIN')
    return
  }

  // 读取预热 URL 列表
  const fs = await import('fs')
  const warmupFile = process.env.WARMUP_URLS_FILE || 'warmup-urls.txt'
  let pathsToPush = DEFAULT_PATHS.map(p => `https://${cdnDomain}${p}`)

  if (fs.existsSync(warmupFile)) {
    const urls = fs.readFileSync(warmupFile, 'utf8')
      .split('\n')
      .map(line => line.trim())
      .filter(line => line.startsWith('https://'))
    if (urls.length > 0) {
      pathsToPush = urls
    }
  }

  try {
    // 动态导入腾讯云 CDN SDK
    const tencentcloud = await import('tencentcloud-sdk-nodejs-cdn')
    const CdnClient = tencentcloud.cdn.v20180606.Client

    // 创建客户端
    const client = new CdnClient({
      credential: {
        secretId,
        secretKey
      },
      region: '',
      profile: {
        httpProfile: {
          endpoint: 'cdn.tencentcloudapi.com'
        }
      }
    })

    // ========== 第一步：刷新缓存 ==========
    // 目录刷新会递归覆盖站点根下所有文件
    console.log(`🚀 正在刷新 CDN: https://${cdnDomain}/`)

    const flushResult = await client.PurgePathCache({
      Paths: [`https://${cdnDomain}/`],
      FlushType: 'flush'
    })

    console.log('✅ CDN 刷新任务已提交:')
    console.log(`   任务 ID: ${flushResult.TaskId}`)
    console.log(`   刷新路径: https://${cdnDomain}/（全站目录刷新）`)

    // ========== 第二步：预热关键页面 ==========
    console.log(`\n🔥 正在预热关键页面（共 ${pathsToPush.length} 条）...`)

    // 分批预热（每次最多 500 条）
    const batchSize = 500
    for (let i = 0; i < pathsToPush.length; i += batchSize) {
      const batch = pathsToPush.slice(i, i + batchSize)

      const pushResult = await client.PushUrlsCache({
        Urls: batch,
        Area: 'mainland'  // 预热至境内节点
      })

      console.log('✅ CDN 预热任务已提交:')
      console.log(`   任务 ID: ${pushResult.TaskId}`)
      console.log(`   预热 URL (${i + 1}-${i + batch.length}/${pathsToPush.length}):`)
      batch.forEach(u => console.log(`     - ${u}`))
    }

    console.log('\n🎉 CDN 刷新与预热完成！')
    console.log('💡 提示: 预热任务需要一定时间生效，请稍后验证访问速度')

  } catch (error) {
    console.error('❌ CDN 操作失败:', error.message)
    if (error.code) {
      console.error(`   错误码: ${error.code}`)
    }
    // 不抛出错误，避免中断部署流程
  }
}

// 执行刷新与预热
refreshCDN()
