using System;
using System.IO;
using System.Reflection;

namespace Vrcrafter.Bootstrap
{
    public static class AssemblyResolver
    {
        private static readonly object SyncRoot = new object();
        private static string PayloadDirectory;
        private static bool Installed;

        public static void Install(string payloadDirectory)
        {
            if (String.IsNullOrWhiteSpace(payloadDirectory))
            {
                throw new ArgumentException("A payload directory is required.", "payloadDirectory");
            }

            lock (SyncRoot)
            {
                if (Installed)
                {
                    return;
                }

                PayloadDirectory = Path.GetFullPath(payloadDirectory);
                AppDomain.CurrentDomain.AssemblyResolve += Resolve;
                Installed = true;
                ManagedLog.Write("RESOLVER_INSTALL path=" + PayloadDirectory);
            }
        }

        private static Assembly Resolve(object sender, ResolveEventArgs args)
        {
            foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                if (String.Equals(assembly.FullName, args.Name, StringComparison.Ordinal))
                {
                    ManagedLog.Write("RESOLVE_LOADED name=" + args.Name
                        + " path=" + assembly.Location);
                    return assembly;
                }
            }

            AssemblyName requested = new AssemblyName(args.Name);
            string simpleName = requested.Name;
            if (String.IsNullOrEmpty(simpleName)
                || simpleName == "."
                || simpleName == ".."
                || simpleName != Path.GetFileName(simpleName)
                || simpleName.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0)
            {
                return null;
            }

            string payloadDirectory = PayloadDirectory;
            string path = Path.Combine(payloadDirectory, simpleName + ".dll");
            if (!File.Exists(path))
            {
                return null;
            }

            Assembly loaded = Assembly.LoadFrom(path);
            ManagedLog.Write("RESOLVE_LOAD name=" + args.Name + " path=" + path);
            return loaded;
        }
    }
}
