import { TrendingUp, BarChart3, PieChart, MapPin, Users, ShoppingCart } from 'lucide-react';

interface Props {
  onQuestionClick: (question: string) => void;
}

const STARTERS = [
  {
    icon: TrendingUp,
    title: '最近30天各渠道销售额对比',
    description: '了解各销售渠道的业绩表现',
    color: 'text-blue-500',
    bg: 'bg-blue-50',
  },
  {
    icon: MapPin,
    title: '哪个地区的退款率最高？',
    description: '分析各地区退款分布情况',
    color: 'text-amber-500',
    bg: 'bg-amber-50',
  },
  {
    icon: Users,
    title: '新用户注册转化趋势如何？',
    description: '查看用户增长和转化漏斗',
    color: 'text-green-500',
    bg: 'bg-green-50',
  },
  {
    icon: ShoppingCart,
    title: '本月订单量环比变化',
    description: '对比分析订单量增长趋势',
    color: 'text-purple-500',
    bg: 'bg-purple-50',
  },
  {
    icon: BarChart3,
    title: '退款率怎么样？',
    description: '查看整体退款率及退款原因',
    color: 'text-red-500',
    bg: 'bg-red-50',
  },
  {
    icon: PieChart,
    title: '各地区订单量排名如何？',
    description: '了解各地区的订单分布',
    color: 'text-indigo-500',
    bg: 'bg-indigo-50',
  },
];

export function StarterCards({ onQuestionClick }: Props) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-4 py-8">
      <div className="text-center mb-8">
        <h2 className="text-xl font-semibold text-slate-800 mb-2">开始探索数据</h2>
        <p className="text-sm text-slate-500">
          选择一个问题开始，或直接在下方输入你的数据查询
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 max-w-3xl w-full">
        {STARTERS.map((item, i) => {
          const Icon = item.icon;
          return (
            <button
              key={i}
              onClick={() => onQuestionClick(item.title)}
              className="starter-card flex flex-col items-start gap-2.5 p-4 rounded-xl border border-slate-200 bg-white text-left hover:border-slate-300"
            >
              <div className={`w-8 h-8 rounded-lg ${item.bg} flex items-center justify-center`}>
                <Icon size={16} className={item.color} />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-800 leading-snug">{item.title}</p>
                <p className="text-xs text-slate-500 mt-1">{item.description}</p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}