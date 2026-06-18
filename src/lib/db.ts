import { PrismaClient } from '@prisma/client'
import path from 'path'

// Resolve the SQLite database path relative to the project root at runtime.
// This makes the app portable — it works regardless of where the project is
// cloned (sandbox, local Mac, CI, etc.) instead of being hard-coded to an
// absolute path that only exists in one environment.
//
// Note: Prisma's CLI (db:push / migrate) resolves the `DATABASE_URL` in .env
// relative to the prisma/ directory, so .env uses `file:../db/custom.db` to
// point at the same <project-root>/db/custom.db file. The override below
// ensures the runtime client agrees, avoiding the well-known Prisma SQLite
// relative-path asymmetry between CLI and runtime.
const dbPath = path.join(process.cwd(), 'db', 'custom.db')

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined
}

export const db =
  globalForPrisma.prisma ??
  new PrismaClient({
    log: ['query'],
    datasources: {
      db: { url: `file:${dbPath}` },
    },
  })

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = db
