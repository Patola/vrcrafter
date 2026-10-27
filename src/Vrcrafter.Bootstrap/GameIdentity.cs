using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading;

namespace Vrcrafter.Bootstrap
{
    public static class GameIdentity
    {
        private const string ExpectedExecutable = "Planet Crafter.exe";
        private const string ExpectedUnityVersion = "6000.3.2f1";
        private const string ExpectedAssemblyHash =
            "3d7457446cbbed551f938b5271f294f45ec100e1f295eeba9b0884b3cdd9191e";
        private const int UnityVersionReadLimit = 64 * 1024;
        private const int GameAssemblyWaitAttempts = 1200;
        private const int GameAssemblyWaitDelayMilliseconds = 100;

        public static bool Validate()
        {
            string actualHash = "<unavailable>";
            bool accepted = false;

            try
            {
                string executablePath;
                using (Process process = Process.GetCurrentProcess())
                {
                    executablePath = process.MainModule.FileName;
                }

                Assembly gameAssembly = WaitForGameAssembly();
                if (gameAssembly == null)
                {
                    ManagedLog.Write("IDENTITY_DETAIL Assembly-CSharp is not loaded");
                }
                else
                {
                    ManagedLog.Write("GAME_ASSEMBLY " + gameAssembly.FullName
                        + " path=" + gameAssembly.Location);
                    actualHash = ComputeSha256(gameAssembly.Location);
                    bool executableMatches = String.Equals(Path.GetFileName(executablePath),
                        ExpectedExecutable, StringComparison.OrdinalIgnoreCase);
                    bool unityMatches = HasExpectedUnityVersion(executablePath);
                    accepted = executableMatches && unityMatches
                        && String.Equals(actualHash, ExpectedAssemblyHash,
                            StringComparison.Ordinal);
                    ManagedLog.Write("IDENTITY_DETAIL executable=" + executableMatches
                        + " unity=" + unityMatches);
                }
            }
            catch (Exception ex)
            {
                ManagedLog.Write("IDENTITY_ERROR " + ex);
            }

            ManagedLog.Write("IDENTITY_HASH actual=" + actualHash);
            ManagedLog.Write(accepted ? "IDENTITY_ACCEPT" : "IDENTITY_REJECT");
            return accepted;
        }

        private static Assembly WaitForGameAssembly()
        {
            Assembly gameAssembly = FindLoadedGameAssembly();
            if (gameAssembly != null)
            {
                return gameAssembly;
            }

            ManagedLog.Write("IDENTITY_WAIT Assembly-CSharp timeout=120s");
            for (int attempt = 0; attempt < GameAssemblyWaitAttempts; attempt++)
            {
                Thread.Sleep(GameAssemblyWaitDelayMilliseconds);
                gameAssembly = FindLoadedGameAssembly();
                if (gameAssembly != null)
                {
                    ManagedLog.Write("IDENTITY_WAIT_READY Assembly-CSharp");
                    return gameAssembly;
                }
            }

            ManagedLog.Write("IDENTITY_WAIT_TIMEOUT Assembly-CSharp after=120s");
            return null;
        }

        private static Assembly FindLoadedGameAssembly()
        {
            foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                if (String.Equals(assembly.GetName().Name, "Assembly-CSharp",
                    StringComparison.Ordinal))
                {
                    return assembly;
                }
            }

            return null;
        }

        private static bool HasExpectedUnityVersion(string executablePath)
        {
            string path = Path.Combine(Path.GetDirectoryName(executablePath),
                "Planet Crafter_Data", "globalgamemanagers");
            byte[] buffer = new byte[UnityVersionReadLimit];
            int count = 0;

            using (FileStream stream = File.OpenRead(path))
            {
                while (count < buffer.Length)
                {
                    int read = stream.Read(buffer, count, buffer.Length - count);
                    if (read == 0)
                    {
                        break;
                    }

                    count += read;
                }
            }

            byte[] expected = Encoding.ASCII.GetBytes(ExpectedUnityVersion);
            for (int offset = 0; offset <= count - expected.Length; offset++)
            {
                bool matches = true;
                for (int index = 0; index < expected.Length; index++)
                {
                    if (buffer[offset + index] != expected[index])
                    {
                        matches = false;
                        break;
                    }
                }

                if (matches)
                {
                    return true;
                }
            }

            return false;
        }

        private static string ComputeSha256(string path)
        {
            byte[] hash;
            using (SHA256 algorithm = SHA256.Create())
            using (FileStream stream = File.OpenRead(path))
            {
                hash = algorithm.ComputeHash(stream);
            }

            StringBuilder hex = new StringBuilder(hash.Length * 2);
            foreach (byte value in hash)
            {
                hex.Append(value.ToString("x2"));
            }

            return hex.ToString();
        }
    }
}
