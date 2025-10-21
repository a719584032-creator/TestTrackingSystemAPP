import screen_brightness_control as sbc
import time


def monitor_display_status(target_off_cycles):
    """
    监控显示器状态，当连续关闭次数达到目标次数时退出。

    :param target_off_cycles: 显示器连续关闭的目标次数
    """
    previous_brightness = None
    off_cycle_count = 0
    was_display_on = True

    while off_cycle_count < target_off_cycles:
        try:
            # 获取当前屏幕亮度
            current_brightness = sbc.get_brightness(display=0)  # 假设只有一个显示器
            print(f"当前屏幕亮度：{current_brightness}")
            if current_brightness == 0:
                raise Exception("Brightness is 0, assuming display is off.")

            if previous_brightness is None:
                previous_brightness = current_brightness

            # 检测屏幕关闭状态
            if current_brightness == 0:
                if was_display_on:
                    off_cycle_count += 1
                    print(f"显示器关闭周期完成: {off_cycle_count} 次")
                was_display_on = False
            else:
                was_display_on = True

            previous_brightness = current_brightness

        except Exception as e:
            # 当无法获取亮度时，假定屏幕已关闭
            print(f"无法获取亮度，假定屏幕已关闭: {e}")
            if was_display_on:
                off_cycle_count += 1
                print(f"显示器关闭周期完成: {off_cycle_count} 次")
            was_display_on = False

        time.sleep(5)  # 每5秒检测一次

    print("目标显示器关闭周期次数已达到，退出监控。")


# 示例用法
if __name__ == "__main__":
    monitor_display_status(3)
