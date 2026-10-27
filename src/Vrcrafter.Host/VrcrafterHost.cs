using System;
using System.Threading;
using UnityEngine;

namespace Vrcrafter.Host
{
    public class VrcrafterHost : MonoBehaviour
    {
        private static Action<string> LogSink = delegate { };
        private GcStressDiagnostic gcStress;
        private int updates;

        public static void ConfigureLogging(Action<string> logSink)
        {
            if (logSink == null)
            {
                throw new ArgumentNullException("logSink");
            }

            LogSink = logSink;
        }

        public static void Log(string message)
        {
            LogSink(message);
        }

        public void Update()
        {
            updates++;
            if (updates <= 3 || (gcStress != null && gcStress.ShouldLogTick()))
            {
                LogSink("HOST_UPDATE tick=" + updates
                    + " thread=" + Thread.CurrentThread.ManagedThreadId);
            }

            MainThreadQueue.RunPending();
            if (gcStress == null)
            {
                gcStress = new GcStressDiagnostic(LogSink);
                gcStress.Start();
            }
        }

        private void OnDestroy()
        {
            LogSink("HOST_DESTROY thread=" + Thread.CurrentThread.ManagedThreadId);
        }
    }
}
