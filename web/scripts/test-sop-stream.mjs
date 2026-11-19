import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const build = mkdtempSync(join(tmpdir(), "sop-stream-tests-"));
try {
  execFileSync(process.execPath, [
    join(root, "node_modules/typescript/bin/tsc"),
    "--ignoreConfig",
    "--target", "es2023", "--lib", "ES2023,DOM,DOM.Iterable",
    "--module", "commonjs", "--moduleResolution", "node",
    "--ignoreDeprecations", "6.0", "--strict", "--skipLibCheck",
    "--outDir", build,
    join(root, "src/sop/sop-sse.ts"),
    join(root, "src/sop/sop-api.ts"),
    join(root, "src/sop/sop-task-stream.ts"),
  ], { cwd: root, stdio: "inherit" });
  execFileSync(process.execPath, ["--test", join(root, "tests/sop-stream.test.cjs")], {
    cwd: root,
    stdio: "inherit",
    env: { ...process.env, SOP_STREAM_TEST_BUILD: build },
  });
} finally {
  rmSync(build, { recursive: true, force: true });
}
