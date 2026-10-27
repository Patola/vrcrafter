using System;
using System.Diagnostics;
using System.Threading;

namespace Vrcrafter.Host
{
    internal sealed class GcStressDiagnostic
    {
        private readonly Action<string> log;
        private readonly Stopwatch stopwatch = new Stopwatch();
        private int running;
        private long lastTickBucket = -1;

        internal GcStressDiagnostic(Action<string> log)
        {
            this.log = log;
        }

        internal void Start()
        {
            Volatile.Write(ref running, 1);
            Thread worker = new Thread(Run);
            worker.IsBackground = true;
            worker.Name = "Vrcrafter GC stress";
            worker.Start();
        }

        internal bool ShouldLogTick()
        {
            if (Volatile.Read(ref running) == 0)
            {
                return false;
            }

            long bucket = stopwatch.ElapsedMilliseconds / 1000;
            if (bucket == lastTickBucket)
            {
                return false;
            }

            lastTickBucket = bucket;
            return true;
        }

        private void Run()
        {
            stopwatch.Start();
            log("GC_STRESS_START duration=30s thread="
                + Thread.CurrentThread.ManagedThreadId);
            long allocations = 0;
            int callbacks = 0;
            long nextCallback = 0;

            try
            {
                while (stopwatch.ElapsedMilliseconds < 30000)
                {
                    for (int index = 0; index < 1024; index++)
                    {
                        byte[] value = new byte[256];
                        GC.KeepAlive(value);
                    }

                    allocations += 1024;
                    if (stopwatch.ElapsedMilliseconds >= nextCallback)
                    {
                        int callback = ++callbacks;
                        MainThreadQueue.Post(delegate
                        {
                            log("WORKER_DISPATCH source=gc-stress callback=" + callback
                                + " elapsed_ms=" + stopwatch.ElapsedMilliseconds
                                + " thread=" + Thread.CurrentThread.ManagedThreadId);
                        });
                        nextCallback += 250;
                    }

                    Thread.Sleep(1);
                }

                Volatile.Write(ref running, 0);
                long duration = stopwatch.ElapsedMilliseconds;
                long allocated = allocations;
                int callbackCount = callbacks;
                MainThreadQueue.Post(delegate
                {
                    log("GC_STRESS_OK duration_ms=" + duration + " allocations=" + allocated
                        + " callbacks=" + callbackCount + " thread="
                        + Thread.CurrentThread.ManagedThreadId);
                });
            }
            catch (Exception ex)
            {
                Volatile.Write(ref running, 0);
                MainThreadQueue.Post(delegate
                {
                    log("GC_STRESS_ERROR " + ex.GetType().FullName + " " + ex.Message);
                });
            }
        }
    }
}
