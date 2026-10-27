using System;
using System.Threading;
using UnityEngine;

namespace Vrcrafter.Host
{
    public class VrcrafterHost : MonoBehaviour
    {
        private static Action<string> LogSink = delegate { };
        private int updates;

        public static void ConfigureLogging(Action<string> logSink)
        {
            if (logSink == null)
            {
                throw new ArgumentNullException("logSink");
            }

            LogSink = logSink;
        }

        public void Update()
        {
            updates++;
            if (updates <= 3)
            {
                LogSink("HOST_UPDATE tick=" + updates
                    + " thread=" + Thread.CurrentThread.ManagedThreadId);
            }

            MainThreadQueue.RunPending();
        }

        private void OnDestroy()
        {
            LogSink("HOST_DESTROY thread=" + Thread.CurrentThread.ManagedThreadId);
        }
    }
}
