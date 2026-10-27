using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Threading;
using BepInEx;
using BepInEx.Bootstrap;
using BepInEx.Configuration;
using BepInEx.Logging;
using Vrcrafter.Host;

namespace Vrcrafter.BepInExBridge
{
    public static class ChainloaderBridge
    {
        private static readonly object SyncRoot = new object();
        private static string[] SearchDirectories;
        private static int StartScheduled;

        public static void Start()
        {
            if (!String.Equals(Environment.GetEnvironmentVariable("VRCRAFTER_BEPINEX"), "1",
                StringComparison.Ordinal)
                || Interlocked.Exchange(ref StartScheduled, 1) != 0)
            {
                return;
            }

            MainThreadQueue.Post(RunOnMainThread);
        }

        private static void RunOnMainThread()
        {
            try
            {
                string payload = Environment.GetEnvironmentVariable("VRCRAFTER_PAYLOAD");
                if (String.IsNullOrWhiteSpace(payload))
                {
                    throw new InvalidOperationException("VRCRAFTER_PAYLOAD is unavailable.");
                }

                string executablePath;
                using (Process process = Process.GetCurrentProcess())
                {
                    executablePath = process.MainModule.FileName;
                }

                string gameRoot = Path.GetDirectoryName(executablePath);
                string managedPath = Path.Combine(gameRoot, "Planet Crafter_Data", "Managed");
                string bepinRoot = Path.Combine(Path.GetFullPath(payload), "bepinex");
                string corePath = Path.Combine(bepinRoot, "core");
                string pluginPath = Path.Combine(bepinRoot, "plugins");

                Directory.CreateDirectory(bepinRoot);
                InstallResolver(corePath, managedPath, pluginPath);
                InitializePaths(executablePath, bepinRoot, managedPath, corePath, pluginPath);
                PreloadCriticalAssemblies(corePath);
                ConfigureAndStart(executablePath, pluginPath);
            }
            catch (Exception ex)
            {
                VrcrafterHost.Log("BEPINEX_CHAINLOADER_ERROR " + ex);
            }
        }

        private static void InstallResolver(string corePath, string managedPath, string pluginPath)
        {
            lock (SyncRoot)
            {
                SearchDirectories = new[]
                {
                    Path.GetFullPath(corePath),
                    Path.GetFullPath(managedPath),
                    Path.GetFullPath(pluginPath)
                };
                AppDomain.CurrentDomain.AssemblyResolve += Resolve;
            }
        }

        private static Assembly Resolve(object sender, ResolveEventArgs args)
        {
            string simpleName = new AssemblyName(args.Name).Name;
            foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                if (String.Equals(assembly.GetName().Name, simpleName, StringComparison.Ordinal))
                {
                    return assembly;
                }
            }

            foreach (string directory in SearchDirectories)
            {
                string path = Path.Combine(directory, simpleName + ".dll");
                if (File.Exists(path))
                {
                    return Assembly.LoadFrom(path);
                }
            }

            return null;
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        private static void InitializePaths(string executablePath, string bepinRoot,
            string managedPath, string corePath, string pluginPath)
        {
            MethodInfo setExecutablePath = typeof(Paths).GetMethod("SetExecutablePath",
                BindingFlags.Static | BindingFlags.NonPublic);
            MethodInfo setPluginPath = typeof(Paths).GetMethod("SetPluginPath",
                BindingFlags.Static | BindingFlags.NonPublic);
            if (setExecutablePath == null || setPluginPath == null)
            {
                throw new MissingMethodException("Pinned BepInEx path initialization is unavailable.");
            }

            setExecutablePath.Invoke(null, new object[]
            {
                executablePath, bepinRoot, managedPath, new[] { corePath, managedPath, pluginPath }
            });
            setPluginPath.Invoke(null, new object[] { pluginPath });
            VrcrafterHost.Log("BEPINEX_PATHS root=" + Paths.BepInExRootPath
                + " assemblyDirectory=" + Paths.BepInExAssemblyDirectory
                + " pluginPath=" + Paths.PluginPath);
        }

        private static void PreloadCriticalAssemblies(string corePath)
        {
            string[] criticalAssemblies =
            {
                "Mono.Cecil",
                "0Harmony",
                "MonoMod.Utils",
                "MonoMod.RuntimeDetour",
                "BepInEx"
            };

            foreach (string simpleName in criticalAssemblies)
            {
                string path = Path.Combine(corePath, simpleName + ".dll");
                if (!File.Exists(path))
                {
                    throw new FileNotFoundException("Pinned BepInEx assembly is missing.", path);
                }

                AssemblyName matchedName = AssemblyName.GetAssemblyName(path);
                if (!String.Equals(matchedName.Name, simpleName, StringComparison.Ordinal))
                {
                    throw new InvalidOperationException("BepInEx assembly identity mismatch: " + path);
                }

                Assembly.LoadFrom(path);
            }
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        private static void ConfigureAndStart(string executablePath, string pluginPath)
        {
            string controlPath = Path.Combine(pluginPath, "Vrcrafter.BepInExControl.dll");
            if (!File.Exists(controlPath))
            {
                throw new FileNotFoundException("The unmodified control plugin is missing.", controlPath);
            }

            PropertyInfo coreConfigProperty = typeof(ConfigFile).GetProperty("CoreConfig",
                BindingFlags.Static | BindingFlags.NonPublic);
            ConfigFile coreConfig = coreConfigProperty == null
                ? null : coreConfigProperty.GetValue(null, null) as ConfigFile;
            if (coreConfig == null)
            {
                throw new InvalidOperationException("Pinned BepInEx core configuration is unavailable.");
            }

            coreConfig.Bind("Chainloader", "HideManagerGameObject", true).Value = true;
            coreConfig.Bind("Logging.Disk", "Enabled", false).Value = false;
            Chainloader.Initialize(null, false, null);
            VrcrafterHost.Log("BEPINEX_PATHS_AFTER_INIT root=" + Paths.BepInExRootPath
                + " assemblyDirectory=" + Paths.BepInExAssemblyDirectory
                + " pluginPath=" + Paths.PluginPath);
            Chainloader.Start();

            PluginInfo control;
            if (!Chainloader.PluginInfos.TryGetValue("com.github.patola.vrcrafter.control", out control)
                || control.Instance == null)
            {
                throw new InvalidOperationException("BepInEx did not instantiate the control plugin.");
            }

            string marker = "BEPINEX_CHAINLOADER_OK thread="
                + Thread.CurrentThread.ManagedThreadId;
            VrcrafterHost.Log(marker);
            ManualLogSource log = Logger.CreateLogSource("VRCrafter Chainloader");
            log.LogInfo(marker);
        }
    }
}
