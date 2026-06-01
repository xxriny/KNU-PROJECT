/**
 * 프로덕션 빌드 스크립트 (Windows + macOS)
 *
 * 사용법:
 *   NAVIGATOR_JWT_SECRET=<시크릿> npm run build:prod    # Windows
 *   NAVIGATOR_JWT_SECRET=<시크릿> npm run build:mac     # macOS (Mac에서 실행)
 *   또는 루트에 .env.build 파일 생성 후 NAVIGATOR_JWT_SECRET=<시크릿> 작성
 *
 * Windows 동작:
 *   1. NAVIGATOR_JWT_SECRET → backend/.env 주입
 *   2. Python 3.11 Embeddable 다운로드 → backend/.python/ 셋업
 *   3. pip install -r requirements.txt
 *   4. vite build + electron-builder (NSIS)
 *   5. backend/.env 정리 (기존 파일 아닌 경우)
 *
 * macOS 동작:
 *   1. NAVIGATOR_JWT_SECRET → backend/.env 주입
 *   2. pip3 install pyinstaller + pyinstaller navigator-backend.spec 실행
 *   3. vite build + electron-builder (DMG, 서명 없음)
 *   4. backend/.env 정리
 *
 * 주의:
 *   - macOS 빌드는 반드시 macOS 머신(또는 GitHub Actions macos runner)에서 실행
 *   - PyInstaller는 크로스 컴파일 불가 — macOS 바이너리는 macOS에서만 생성 가능
 *   - 인증서 없이 빌드하면 Gatekeeper가 차단하므로 최초 실행 시 우클릭 → 열기 필요
 */

const { execSync, spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const https = require("https");
const { createWriteStream, mkdirSync } = require("fs");

const ROOT = path.join(__dirname, "..");
const BACKEND_DIR = path.join(ROOT, "backend");
const ENV_PATH = path.join(BACKEND_DIR, ".env");
const BUILD_ENV_PATH = path.join(ROOT, ".env.build");
const PYTHON_DIR = path.join(BACKEND_DIR, ".python");

const IS_MAC = process.platform === "darwin";
const IS_WIN = process.platform === "win32";

// Windows Embeddable Python 설정
const PYTHON_VERSION = "3.11.9";
const PYTHON_EMBED_URL = `https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-embed-amd64.zip`;
const GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py";

// ── 유틸 ──────────────────────────────────────────────────────
function download(url, dest) {
  return new Promise((resolve, reject) => {
    const file = createWriteStream(dest);
    const get = (u) => https.get(u, (res) => {
      if (res.statusCode === 301 || res.statusCode === 302) {
        return get(res.headers.location);
      }
      res.pipe(file);
      file.on("finish", () => file.close(resolve));
    }).on("error", reject);
    get(url);
  });
}

function run(cmd, opts = {}) {
  execSync(cmd, { stdio: "inherit", cwd: ROOT, ...opts });
}

// ── 시크릿 로드 ──────────────────────────────────────────────
let jwtSecret = process.env.NAVIGATOR_JWT_SECRET;

const envSources = [BUILD_ENV_PATH, ENV_PATH];
if (!jwtSecret) {
  for (const src of envSources) {
    if (!fs.existsSync(src)) continue;
    const lines = fs.readFileSync(src, "utf-8").split("\n");
    for (const line of lines) {
      const m = line.match(/^NAVIGATOR_JWT_SECRET=(.+)$/);
      if (m) { jwtSecret = m[1].trim(); break; }
    }
    if (jwtSecret) break;
  }
}

if (!jwtSecret) {
  console.error("\n[build:prod] ❌ NAVIGATOR_JWT_SECRET이 설정되지 않았습니다.");
  console.error("  방법 1: NAVIGATOR_JWT_SECRET=<값> npm run build:prod");
  console.error("  방법 2: 루트에 .env.build 파일 생성 후 NAVIGATOR_JWT_SECRET=<값> 작성\n");
  process.exit(1);
}

// ── backend/.env 생성 ─────────────────────────────────────────
const envAlreadyExisted = fs.existsSync(ENV_PATH);
if (!envAlreadyExisted) {
  console.log("[build:prod] backend/.env 생성 중...");
  fs.writeFileSync(ENV_PATH, `NAVIGATOR_JWT_SECRET=${jwtSecret}\n`, "utf-8");
} else {
  console.log("[build:prod] 기존 backend/.env 사용");
}

// ── macOS: PyInstaller 번들 셋업 ─────────────────────────────
async function setupPythonMac() {
  const distBin = path.join(BACKEND_DIR, "dist", "navigator-backend", "navigator-backend");

  if (fs.existsSync(distBin)) {
    console.log("[build:prod] PyInstaller 번들 이미 존재, 스킵");
    return;
  }

  console.log("\n[build:prod] PyInstaller 설치 중...");
  run("pip3 install pyinstaller --quiet", { cwd: BACKEND_DIR });

  console.log("[build:prod] backend 의존성 설치 중...");
  const reqPath = path.join(BACKEND_DIR, "requirements.txt");
  run(`pip3 install -r "${reqPath}" --quiet`, { cwd: BACKEND_DIR });

  console.log("[build:prod] PyInstaller 번들 빌드 중 (수 분 소요)...\n");
  const specPath = path.join(BACKEND_DIR, "navigator-backend.spec");
  const distPath = path.join(BACKEND_DIR, "dist");
  const buildPath = path.join(BACKEND_DIR, "build");
  run(
    `pyinstaller "${specPath}" --distpath "${distPath}" --workpath "${buildPath}" --noconfirm`,
    { cwd: BACKEND_DIR }
  );

  // 실행 권한 확인
  if (!fs.existsSync(distBin)) {
    throw new Error(
      `PyInstaller 빌드 후 바이너리를 찾을 수 없습니다: ${distBin}\n` +
      "빌드 로그를 확인하세요 (backend/build/ 디렉토리)."
    );
  }
  run(`chmod +x "${distBin}"`);
  console.log("[build:prod] ✅ PyInstaller 번들 완료\n");
}

// ── Windows: Python Embeddable 셋업 ──────────────────────────
async function setupPython() {
  const pythonExe = path.join(PYTHON_DIR, "python.exe");

  if (fs.existsSync(pythonExe)) {
    console.log("[build:prod] Python Embeddable 이미 존재, 스킵");
    return;
  }

  console.log(`\n[build:prod] Python ${PYTHON_VERSION} Embeddable 다운로드 중...`);
  mkdirSync(PYTHON_DIR, { recursive: true });

  const zipPath = path.join(PYTHON_DIR, "python-embed.zip");
  await download(PYTHON_EMBED_URL, zipPath);
  console.log("[build:prod] 다운로드 완료, 압축 해제 중...");

  // Windows 내장 Expand-Archive 사용
  run(`powershell -Command "Expand-Archive -Path '${zipPath}' -DestinationPath '${PYTHON_DIR}' -Force"`);
  fs.unlinkSync(zipPath);

  // ── site-packages 활성화 + backend 경로 추가 ──────────────
  // python311._pth 파일:
  //   - '#import site' 주석 해제 → site-packages 활성화
  //   - '..' 추가 → backend/ 디렉토리를 sys.path에 포함
  //   (Embeddable Python은 PYTHONPATH 환경변수를 무시하므로 ._pth로 직접 지정)
  const pthFile = fs.readdirSync(PYTHON_DIR).find((f) => f.endsWith("._pth"));
  if (pthFile) {
    const pthPath = path.join(PYTHON_DIR, pthFile);
    let content = fs.readFileSync(pthPath, "utf-8");
    content = content.replace("#import site", "import site");
    if (!content.split(/\r?\n/).includes("..")) {
      content = "..\r\n" + content;
    }
    fs.writeFileSync(pthPath, content, "utf-8");
    console.log(`[build:prod] ${pthFile} 업데이트 (site-packages + backend 경로)`);
  }

  // ── pip 설치 ─────────────────────────────────────────────
  console.log("[build:prod] pip 설치 중...");
  const getPipPath = path.join(PYTHON_DIR, "get-pip.py");
  await download(GET_PIP_URL, getPipPath);
  run(`"${pythonExe}" "${getPipPath}" --no-warn-script-location`);
  fs.unlinkSync(getPipPath);

  // ── requirements 설치 ────────────────────────────────────
  console.log("\n[build:prod] 패키지 설치 중 (수 분 소요)...");
  const reqPath = path.join(BACKEND_DIR, "requirements.txt");
  run(`"${pythonExe}" -m pip install -r "${reqPath}" --no-warn-script-location`);

  console.log("[build:prod] ✅ Python 환경 셋업 완료\n");
}

// ── 메인 ─────────────────────────────────────────────────────
(async () => {
  try {
    if (IS_MAC) {
      // ── macOS 빌드 ──────────────────────────────────────────
      if (IS_WIN) {
        // 이 분기는 실제로는 도달하지 않지만 명시적으로 차단
        throw new Error("macOS 빌드는 macOS 머신에서만 실행 가능합니다.");
      }
      await setupPythonMac();

      console.log("[build:prod] Vite 빌드 + electron-builder (DMG) 시작...\n");
      run("npm run build:electron", {
        env: {
          ...process.env,
          CSC_IDENTITY_AUTO_DISCOVERY: "false",  // 인증서 없이 빌드
          CSC_IDENTITY: "",
        },
      });

      console.log("\n[build:prod] ✅ 빌드 완료!");
      console.log("    dist/ 또는 release/ 디렉토리에서 .dmg 파일을 확인하세요.");
      console.log("    ⚠️  서명 없는 빌드: 설치 후 첫 실행 시 우클릭 → 열기 로 실행하세요.");
    } else {
      // ── Windows 빌드 ────────────────────────────────────────
      await setupPython();

      console.log("[build:prod] Vite 빌드 + electron-builder 시작...\n");
      run("npm run build:electron", {
        env: {
          ...process.env,
          CSC_IDENTITY_AUTO_DISCOVERY: "false",
        },
      });

      console.log("\n[build:prod] ✅ 빌드 완료! dist/NAVIGATOR Setup x.x.x.exe 확인하세요.");
    }
  } catch (err) {
    console.error("\n[build:prod] ❌ 빌드 실패:", err.message);
    process.exit(1);
  } finally {
    if (!envAlreadyExisted && fs.existsSync(ENV_PATH)) {
      fs.unlinkSync(ENV_PATH);
      console.log("[build:prod] backend/.env 삭제 완료");
    }
  }
})();
