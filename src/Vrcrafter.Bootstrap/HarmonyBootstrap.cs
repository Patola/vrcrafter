using System;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Threading;
using HarmonyLib;
using UnityEngine;
using Vrcrafter.BepInExBridge;
using Vrcrafter.Host;

namespace Vrcrafter.Bootstrap
{
    public static class HarmonyBootstrap
    {
        private const string OwnerId = "com.github.patola.vrcrafter.loader";
        private static Harmony harmony;
        private static MethodInfo original;
        private static MethodInfo postfix;
        private static int patchReady;
        private static int hostCreationStarted;

        public static void Install()
        {
            Assembly gameAssembly = null;
            foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                if (String.Equals(assembly.GetName().Name, "Assembly-CSharp",
                    StringComparison.Ordinal))
                {
                    gameAssembly = assembly;
                    break;
                }
            }

            if (gameAssembly == null)
            {
                throw new InvalidOperationException("Assembly-CSharp is not loaded.");
            }

            Type dispatcher = gameAssembly.GetType("SpaceCraft.PlayerInputDispatcher", true);
            original = dispatcher.GetMethod("Update",
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (original == null)
            {
                throw new MissingMethodException(dispatcher.FullName, "Update");
            }

            postfix = typeof(HarmonyBootstrap).GetMethod("Postfix",
                BindingFlags.Static | BindingFlags.NonPublic);
            harmony = new Harmony(OwnerId);
            VrcrafterHost.ConfigureLogging(ManagedLog.Write);
            harmony.Patch(original, postfix: new HarmonyMethod(postfix));
            ManagedLog.Write("HARMONY_PATCH owner=" + OwnerId
                + " thread=" + Thread.CurrentThread.ManagedThreadId);

            MainThreadQueue.Post(delegate
            {
                ManagedLog.Write("WORKER_DISPATCH thread="
                    + Thread.CurrentThread.ManagedThreadId);
            });
            Volatile.Write(ref patchReady, 1);
        }

        private static void Postfix()
        {
            int threadId = Thread.CurrentThread.ManagedThreadId;
            if (Volatile.Read(ref patchReady) == 0
                || Interlocked.Exchange(ref hostCreationStarted, 1) != 0)
            {
                return;
            }

            MainThreadQueue.Post(delegate
            {
                ManagedLog.Write("ORIGINAL_CONTINUES thread=" + threadId);
            });

            try
            {
                GameObject hostObject = new GameObject("Vrcrafter.Host");
                hostObject.AddComponent<VrcrafterHost>();
                UnityEngine.Object.DontDestroyOnLoad(hostObject);
                ManagedLog.Write("HOST_CREATE thread=" + threadId);
                harmony.Unpatch(original, postfix);
                if (String.Equals(Environment.GetEnvironmentVariable("VRCRAFTER_BEPINEX"), "1",
                    StringComparison.Ordinal))
                {
                    StartOptionalChainloader();
                }
            }
            catch (Exception ex)
            {
                ManagedLog.Write("EXCEPTION " + ex);
            }
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        private static void StartOptionalChainloader()
        {
            ChainloaderBridge.Start();
        }
    }
}
