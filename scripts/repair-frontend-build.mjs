import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const frontendDir = path.join(repoRoot, "frontend");
const nodeModulesDir = path.join(frontendDir, "node_modules");
const packageLockPath = path.join(frontendDir, "package-lock.json");
const distDir = path.join(frontendDir, "dist");
const typescriptTscPath = path.join(frontendDir, "node_modules", "typescript", "lib", "tsc.js");
const npmCmd = process.platform === "win32" ? "npm.cmd" : "npm";

function logStep(step, message) {
  console.log(`\n[${step}] ${message}`);
}

async function removeIfExists(targetPath) {
  try {
    await fs.rm(targetPath, { recursive: true, force: true });
    return true;
  } catch (error) {
    throw new Error(`Failed to remove ${targetPath}: ${error.message}`);
  }
}

async function exists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

function runCommand(command, args, options = {}) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      cwd: options.cwd ?? repoRoot,
      env: { ...process.env, ...(options.env ?? {}) },
      shell: process.platform === "win32",
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (data) => {
      const text = data.toString();
      stdout += text;
      process.stdout.write(text);
    });

    child.stderr.on("data", (data) => {
      const text = data.toString();
      stderr += text;
      process.stderr.write(text);
    });

    child.on("close", (code) => {
      resolve({ code, stdout, stderr });
    });
  });
}

async function main() {
  console.log("Frontend repair/build verification started");
  console.log(`Repository: ${repoRoot}`);
  console.log(`Frontend: ${frontendDir}`);

  try {
    logStep(1, "Removing corrupted frontend dependencies");
    const removedNodeModules = await removeIfExists(nodeModulesDir);
    const removedPackageLock = await removeIfExists(packageLockPath);
    console.log(`- Removed node_modules: ${removedNodeModules ? "yes" : "no"}`);
    console.log(`- Removed package-lock.json: ${removedPackageLock ? "yes" : "no"}`);

    logStep(2, "Reinstalling frontend dependencies with npm");
    const install = await runCommand(npmCmd, ["install"], { cwd: frontendDir });
    if (install.code !== 0) {
      throw new Error(`npm install failed with exit code ${install.code}`);
    }

    logStep(3, "Verifying TypeScript installation");
    const hasTsc = await exists(typescriptTscPath);
    if (!hasTsc) {
      throw new Error(`TypeScript verification failed: missing ${typescriptTscPath}`);
    }
    const npmLs = await runCommand(npmCmd, ["ls", "typescript", "--depth=0"], { cwd: frontendDir });
    if (npmLs.code !== 0) {
      throw new Error(`npm ls typescript failed with exit code ${npmLs.code}`);
    }
    console.log(`- Found ${typescriptTscPath}`);

    logStep(4, "Running frontend build");
    const build = await runCommand(npmCmd, ["run", "build"], { cwd: frontendDir });
    if (build.code !== 0) {
      throw new Error(`npm run build failed with exit code ${build.code}`);
    }
    console.log("✅ Frontend build successful");

    logStep(5, "Cleaning build artifacts");
    const distExisted = await exists(distDir);
    if (distExisted) {
      await removeIfExists(distDir);
      console.log("- Removed frontend/dist");
    } else {
      console.log("- No frontend/dist artifact to remove");
    }

    logStep(6, "Final status");
    console.log("Repair completed successfully.");
    process.exitCode = 0;
  } catch (error) {
    logStep("ERROR", "Frontend repair/build failed");
    console.error(error.message);
    console.error("❌ Frontend build failed");
    process.exitCode = 1;
  }
}

await main();
