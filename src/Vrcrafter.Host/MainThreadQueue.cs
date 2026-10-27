using System;
using System.Collections.Concurrent;

namespace Vrcrafter.Host
{
    public static class MainThreadQueue
    {
        private static readonly ConcurrentQueue<Action> Queue = new ConcurrentQueue<Action>();

        public static void Post(Action action)
        {
            if (action == null)
            {
                throw new ArgumentNullException("action");
            }

            Queue.Enqueue(action);
        }

        public static void RunPending()
        {
            int count = 0;
            Action action;
            while (count < 64 && Queue.TryDequeue(out action))
            {
                action();
                count++;
            }
        }
    }
}
