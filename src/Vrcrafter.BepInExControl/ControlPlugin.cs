using System;
using System.Reflection;
using System.Threading;
using BepInEx;
using BepInEx.Logging;
using HarmonyLib;

namespace Vrcrafter.BepInExControl
{
    [BepInPlugin(PluginGuid, "VRCrafter Control", "1.0.0")]
    public sealed class ControlPlugin : BaseUnityPlugin
    {
        public const string PluginGuid = "com.github.patola.vrcrafter.control";
        private static ManualLogSource PluginLog;
        private static int HarmonyMarkerWritten;

        private void Awake()
        {
            PluginLog = Logger;
            Logger.LogInfo("BEPINEX_CONTROL_OK");

            MethodInfo original = typeof(SpaceCraft.PlayerInputDispatcher).GetMethod("Update",
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (original == null)
            {
                throw new MissingMethodException(typeof(SpaceCraft.PlayerInputDispatcher).FullName,
                    "Update");
            }

            MethodInfo postfix = typeof(ControlPlugin).GetMethod("Postfix",
                BindingFlags.Static | BindingFlags.NonPublic);
            Harmony harmony = new Harmony(PluginGuid);
            harmony.Patch(original, postfix: new HarmonyMethod(postfix));
        }

        private static void Postfix()
        {
            if (Interlocked.Exchange(ref HarmonyMarkerWritten, 1) == 0)
            {
                PluginLog.LogInfo("BEPINEX_CONTROL_HARMONY_OK ORIGINAL_CONTINUES");
            }
        }
    }
}
